
from typing import TypedDict
from uuid import UUID

from langgraph.graph import StateGraph, START, END

from app.database import get_connection
from app.metrics_client import get_monitoring_evidence
from app.logs_client import get_log_evidence
from app.ai_client import analyze_incident, safe_collect


# Data shared between workflow steps
class InvestigationState(TypedDict, total=False):
    incident_id: str
    incident: dict
    monitoring: dict
    logs: dict
    analysis: str


# NODE 1: Load incident from PostgreSQL
def fetch_incident(state: InvestigationState):

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM incidents WHERE id = %s",
                (UUID(state["incident_id"]),)
            )
            incident = cur.fetchone()

    if incident is None:
        raise LookupError("Incident not found")

    return {"incident": incident}


# NODE 2: Collect monitoring evidence
def collect_evidence(state: InvestigationState):

    monitoring = safe_collect(
        get_monitoring_evidence
    )

    logs = safe_collect(
        get_log_evidence
    )

    return {
        "monitoring": monitoring,
        "logs": logs
    }


# NODE 3: Generate AI report
def generate_analysis(state: InvestigationState):

    report = analyze_incident(
        incident=state["incident"],
        monitoring=state["monitoring"],
        log_evidence=state["logs"]
    )

    return {"analysis": report}


# Build workflow
builder = StateGraph(InvestigationState)

builder.add_node("fetch_incident", fetch_incident)
builder.add_node("collect_evidence", collect_evidence)
builder.add_node("generate_analysis", generate_analysis)

builder.add_edge(START, "fetch_incident")
builder.add_edge("fetch_incident", "collect_evidence")
builder.add_edge("collect_evidence", "generate_analysis")
builder.add_edge("generate_analysis", END)

investigation_graph = builder.compile()
