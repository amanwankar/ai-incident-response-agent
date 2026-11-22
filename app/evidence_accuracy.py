"""Incident-time, read-only evidence gathering. Never invent missing metrics/logs.

The Prometheus database must actually retain the incident timestamps. A new
Prometheus instance cannot recover historic metric samples from the old one.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://127.0.0.1:9090').rstrip('/')
LOG_PATH = Path(os.getenv('AIOPS_LOG_PATH', 'logs/fastapi.log'))
ISO_PREFIX = re.compile(r'20\d\d-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?')

QUERIES = {
    'fastapi_up': 'up{job="fastapi"}',
    'http_5xx_increase': 'sum(increase(http_server_errors_total{job="fastapi"}[5m]))',
    'request_rate_per_minute': 'sum(rate(http_requests_total{job="fastapi"}[2m])) * 60',
}


def normalize_time(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Naive incident timestamps cannot be used for evidence correlation')
    return value.astimezone(timezone.utc)


def evidence_window(created_at: datetime | str, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Restrict queries to a small window anchored to the incident timestamp."""
    created = normalize_time(created_at)
    upper = normalize_time(now or datetime.now(timezone.utc))
    return created - timedelta(minutes=2), min(created + timedelta(minutes=5), upper)


def parse_log_timestamp(line: str) -> datetime | None:
    try:
        row = json.loads(line)
        if isinstance(row, dict) and row.get('timestamp'):
            return normalize_time(row['timestamp'])
    except (ValueError, TypeError, KeyError):
        pass
    match = ISO_PREFIX.search(line)
    if not match:
        return None
    try:
        return normalize_time(match.group())
    except (ValueError, TypeError):
        return None


def filter_timestamped_logs(lines: list[str], start: datetime, end: datetime, max_entries: int = 20) -> list[str]:
    """Only emit timestamped error-like logs in the incident window.

    Temporal proximity is NOT proof that a log line caused the incident.
    """
    needles = ('error', 'exception', 'traceback', 'status=500', 'status=502', 'status=503', 'status=504')
    matched = []
    for line in lines:
        timestamp = parse_log_timestamp(line)
        if timestamp and start <= timestamp <= end and any(word in line.lower() for word in needles):
            matched.append(line.rstrip()[:800])
    return matched[-max_entries:]


def read_timed_logs(start: datetime, end: datetime) -> dict:
    if not LOG_PATH.exists():
        return {'status': 'unavailable', 'entries': [], 'reason': f'Log file missing: {LOG_PATH}'}
    # Local lab file, bounded bytes so very large logs cannot exhaust RAM.
    with LOG_PATH.open('rb') as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - 2_000_000))
        text = stream.read().decode('utf-8', errors='replace')
    entries = filter_timestamped_logs(text.splitlines(), start, end)
    return {
        'status': 'matched' if entries else 'no_timestamped_matches',
        'entries': entries,
        'reason': 'No matched logs does not prove that no errors occurred.',
        'warning': 'Temporal proximity alone does not prove causation.',
    }


def query_range(expression: str, start: datetime, end: datetime) -> dict:
    if end <= start:
        return {'status': 'unavailable', 'points': [], 'reason': 'Invalid or future incident window'}
    params = urlencode({
        'query': expression,
        'start': str(start.timestamp()),
        'end': str(end.timestamp()),
        'step': '30s',
    })
    url = f'{PROMETHEUS_URL}/api/v1/query_range?{params}'
    try:
        with urlopen(url, timeout=10) as response:
            payload = json.load(response)
        if payload.get('status') != 'success':
            raise ValueError('Prometheus did not return success')
        series = payload.get('data', {}).get('result', [])
        points = []
        for item in series:
            for timestamp, value in item.get('values', []):
                try:
                    numeric = float(value)
                    if numeric == numeric and numeric != float('inf') and numeric != float('-inf'):
                        points.append({'timestamp': float(timestamp), 'value': numeric})
                except (TypeError, ValueError):
                    continue
        return {'status': 'available' if points else 'no_samples', 'points': points[-300:]}
    except (OSError, ValueError, KeyError, TimeoutError) as exc:
        return {'status': 'unavailable', 'points': [], 'reason': str(exc)[:180]}


def nearest_sample(series: dict, when: datetime, max_distance_seconds: int = 75) -> float | None:
    points = series.get('points', [])
    if not points:
        return None
    closest = min(points, key=lambda item: abs(item['timestamp'] - when.timestamp()))
    return closest['value'] if abs(closest['timestamp'] - when.timestamp()) <= max_distance_seconds else None


def collect_incident_evidence(created_at: datetime | str) -> dict:
    created = normalize_time(created_at)
    start, end = evidence_window(created)
    metrics = {key: query_range(query, start, end) for key, query in QUERIES.items()}
    logs = read_timed_logs(start, end)
    summary = {key: nearest_sample(series, created) for key, series in metrics.items()}
    has_historical_evidence = any(value is not None for value in summary.values()) or bool(logs['entries'])
    return {
        'incident_time_utc': created.isoformat(),
        'window_start_utc': start.isoformat(),
        'window_end_utc': end.isoformat(),
        'metric_summary_near_start': summary,
        'metric_coverage': {key: {'status': val['status'], 'sample_count': len(val['points'])} for key, val in metrics.items()},
        'log_evidence': logs,
        'has_time_aligned_evidence': has_historical_evidence,
        'limitations': [
            'Prometheus target job=fastapi may describe a different backend deployment.',
            'Metric values reflect samples near incident creation, not definitive root cause.',
            'Logs are selected by timestamp and severity keywords; correlation is not causation.',
            'New Prometheus storage cannot provide samples from an earlier Prometheus instance.',
        ],
    }
