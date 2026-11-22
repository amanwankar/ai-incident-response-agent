"""A separate, evidence-gated LangGraph investigation endpoint.

Existing /investigate remains unchanged; this endpoint can be rolled back by
removing its router registration from app/main.py.
"""
from __future__ import annotations

import json
import os
from typing import Any, TypedDict
from urllib.request import Request, urlopen
from uuid import UUID

from fastapi import APIRouter, HTTPException
from langgraph.graph import END, StateGraph

from app.database import get_connection
from app.evidence_accuracy import collect_incident_evidence

router = APIRouter()


class VerifiedState(TypedDict, total=False):
    incident_id: str
    incident: dict[str, Any]
    evidence: dict[str, Any]
    hypotheses: list[str]
    checks: list[str]
    ai_status: str


def fetch_incident(state: VerifiedState) -> dict:
    try:
        incident_uuid = UUID(state['incident_id'])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Invalid incident UUID') from exc
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM incidents WHERE id = %s', (incident_uuid,))
            result = cursor.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail='Incident not found')
    return {'incident': dict(result)}


def gather_evidence(state: VerifiedState) -> dict:
    return {'evidence': collect_incident_evidence(state['incident']['created_at'])}


def analyze_evidence(state: VerifiedState) -> dict:
    evidence = state['evidence']
    if not evidence['has_time_aligned_evidence']:
        return {
            'hypotheses': [],
            'checks': ['Collect timestamped logs and metrics when a new alert fires.', 'Verify the service and relevant incident timestamps.'],
            'ai_status': 'skipped: insufficient timestamp-aligned evidence',
        }

    incident = state['incident']
    inputs = {
        'incident': {key: str(incident.get(key)) for key in ('id', 'alertname', 'severity', 'status', 'summary', 'description', 'created_at', 'resolved_at')},
        'evidence': {
            'metric_summary_near_start': evidence['metric_summary_near_start'],
            'metric_coverage': evidence['metric_coverage'],
            'log_entries': evidence['log_evidence']['entries'][:12],
            'limitations': evidence['limitations'],
        },
    }
    prompt = (
        'You are an incident triage assistant, NOT an autonomous root-cause verifier. '
        'Use ONLY the supplied evidence. Respond with a JSON object containing exactly '
        '"hypotheses" (array of at most 3 short strings) and '
        '"recommended_checks" (array of at most 4 short strings). '
        'Every hypothesis must be explicitly conditional. Do not claim any root cause '
        'is proven, do not invent logs or errors, and never suggest destructive actions. '
        'Avoid assuming the metrics describe the same backend instance. '
        'If evidence cannot support a hypothesis, return an empty hypotheses array.\n\n'
        + json.dumps(inputs, default=str)
    )
    endpoint = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/') + '/api/generate'
    request = Request(
        endpoint,
        data=json.dumps({
            'model': os.getenv('OLLAMA_MODEL', 'qwen2.5:1.5b'),
            'prompt': prompt,
            'format': 'json',
            'stream': False,
            'options': {'temperature': 0.1, 'num_predict': 550},
        }).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=210) as response:
            generated = json.load(response)
        parsed = json.loads(generated.get('response', '{}'))
        hypotheses = parsed.get('hypotheses', [])
        checks = parsed.get('recommended_checks', [])
        if not isinstance(hypotheses, list) or not isinstance(checks, list):
            raise ValueError('Unexpected model schema')
        return {
            'hypotheses': [str(x)[:450] for x in hypotheses[:3]],
            'checks': [str(x)[:450] for x in checks[:4]],
            'ai_status': 'generated: hypotheses remain unverified',
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {
            'hypotheses': [],
            'checks': ['Inspect the timestamped evidence manually.'],
            'ai_status': f'unavailable: {type(exc).__name__}',
        }


builder = StateGraph(VerifiedState)
builder.add_node('fetch_incident', fetch_incident)
builder.add_node('collect_incident_time_evidence', gather_evidence)
builder.add_node('generate_cautious_hypotheses', analyze_evidence)
builder.set_entry_point('fetch_incident')
builder.add_edge('fetch_incident', 'collect_incident_time_evidence')
builder.add_edge('collect_incident_time_evidence', 'generate_cautious_hypotheses')
builder.add_edge('generate_cautious_hypotheses', END)
verified_graph = builder.compile()


@router.post('/api/incidents/{incident_id}/investigate-verified')
def investigate_verified(incident_id: str):
    result = verified_graph.invoke({'incident_id': incident_id})
    incident = result['incident']
    evidence = result['evidence']
    summary = evidence['metric_summary_near_start']
    facts = [
        f"Alert: {incident.get('alertname')} ({incident.get('severity')})",
        f"Incident creation (UTC): {evidence['incident_time_utc']}",
        f"Evidence available: {evidence['has_time_aligned_evidence']}",
        f"Metric sample coverage: {evidence['metric_coverage']}",
        f"Timestamp-matched error log entries: {len(evidence['log_evidence']['entries'])}",
    ]
    analysis = 'INCIDENT FACTS (FROM DATABASE / QUERY)\n' + '\n'.join('- ' + x for x in facts)
    analysis += '\n\nAI HYPOTHESES — UNVERIFIED\n'
    analysis += '\n'.join('- Hypothesis (not established): ' + x for x in result['hypotheses']) if result['hypotheses'] else '- No evidence-supported hypothesis generated.'
    analysis += '\n\nRECOMMENDED SAFE CHECKS\n'
    analysis += '\n'.join('- ' + x for x in result['checks'])
    analysis += '\n\nLIMITATIONS\n' + '\n'.join('- ' + x for x in evidence['limitations'])
    return {
        'incident_id': str(incident['id']),
        'status': str(incident['status']),
        'monitoring': {
            'fastapi_up': summary['fastapi_up'],
            'http_5xx_last_5m_estimate': summary['http_5xx_increase'],
            'request_rate_per_minute': summary['request_rate_per_minute'],
        },
        'logs': {'entries': evidence['log_evidence']['entries'], 'status': evidence['log_evidence']['status']},
        'evidence': evidence,
        'ai_status': result['ai_status'],
        'analysis': analysis,
        'note': 'Hypotheses are not verified root causes. Human review is required. Missing historical data is never treated as zero.',
    }
