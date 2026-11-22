
import asyncio
import json
import logging
import time
import uuid

from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Request
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.responses import Response


# ==================================================
# 1. REQUEST ID CONTEXT
# ==================================================

request_id_context = ContextVar("request_id", default="-")


# ==================================================
# 2. STRUCTURED JSON LOGGING
# ==================================================

class JSONFormatter(logging.Formatter):

    def format(self, record):

        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        })


logger = logging.getLogger("incident-agent")
logger.setLevel(logging.INFO)
logger.handlers.clear()

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())

logger.addHandler(handler)
logger.propagate = False


# ==================================================
# 3. FASTAPI APPLICATION
# ==================================================

app = FastAPI(
    title="AI Incident Response Agent",
    description="Production monitoring application",
    version="1.0.0",
)


# ==================================================
# 4. PROMETHEUS METRICS
# ==================================================

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

SERVER_ERRORS = Counter(
    "http_server_errors_total",
    "Total HTTP 5xx errors",
    ["method", "path"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(
        0.005, 0.01, 0.025, 0.05,
        0.1, 0.25, 0.5, 1,
        2.5, 5, 7.5, 10
    ),
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of requests currently processing",
    ["method", "path"],
)

APP_UP = Gauge(
    "application_up",
    "Application health status",
)

APP_UP.set(1)


# ==================================================
# 5. REQUEST MONITORING MIDDLEWARE
# ==================================================

@app.middleware("http")
async def monitor_requests(request: Request, call_next):

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    token = request_id_context.set(request_id)

    start_time = time.perf_counter()

    method = request.method
    path = request.url.path

    # Prevent metrics endpoint from counting itself
    track_request = path != "/metrics"

    status_code = 500

    if track_request:
        REQUESTS_IN_PROGRESS.labels(method, path).inc()

    try:

        response = await call_next(request)

        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception:

        logger.exception("Unhandled application exception")
        raise

    finally:

        duration = time.perf_counter() - start_time

        if track_request:

            REQUEST_COUNT.labels(
                method, path, str(status_code)
            ).inc()

            REQUEST_LATENCY.labels(
                method, path
            ).observe(duration)

            if status_code >= 500:
                SERVER_ERRORS.labels(
                    method, path
                ).inc()

            REQUESTS_IN_PROGRESS.labels(
                method, path
            ).dec()

        logger.info(
            f"{method} {path} "
            f"status={status_code} "
            f"duration={duration:.4f}s"
        )

        request_id_context.reset(token)


# ==================================================
# 6. HEALTH API
# ==================================================

@app.get("/api/health")
async def health_check():

    logger.info("Health check requested")

    return {
        "ok": True,
        "application": "incident-response-agent",
        "status": "healthy",
        "storage": "not-connected-yet",
    }


# ==================================================
# 7. NORMAL ORDERS API
# ==================================================

@app.get("/api/orders")
async def get_orders():

    logger.info("Orders API requested")

    return {
        "total": 3,
        "orders": [
            {
                "id": 101,
                "product": "Laptop",
                "status": "confirmed"
            },
            {
                "id": 102,
                "product": "Mobile",
                "status": "processing"
            },
            {
                "id": 103,
                "product": "Headphones",
                "status": "delivered"
            }
        ]
    }


# ==================================================
# 8. SLOW API - INCIDENT SIMULATION
# ==================================================

@app.get("/api/slow")
async def slow_api(
    seconds: float = Query(default=3, ge=0, le=10)
):

    logger.warning(
        f"Slow API simulation started: delay={seconds}s"
    )

    await asyncio.sleep(seconds)

    return {
        "message": "Slow API completed",
        "delay_seconds": seconds,
    }


# ==================================================
# 9. ERROR API - INCIDENT SIMULATION
# ==================================================

@app.get("/api/error")
async def error_api():

    logger.error("Simulated internal application error")

    raise HTTPException(
        status_code=500,
        detail="Simulated internal server error",
    )


# ==================================================
# 10. PROMETHEUS METRICS ENDPOINT
# ==================================================

@app.get("/metrics")
async def metrics():

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ==================================================
# 10. INCIDENT MANAGEMENT - POSTGRESQL
# ==================================================

from typing import Literal
from pydantic import BaseModel, Field
from psycopg.types.json import Json
from app.database import get_connection


class IncomingAlert(BaseModel):
    status: Literal["firing", "resolved"]
    fingerprint: str = Field(min_length=1)
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    endsAt: str | None = None


class AlertmanagerPayload(BaseModel):
    receiver: str | None = None
    status: str | None = None
    alerts: list[IncomingAlert]


@app.post("/api/alerts/webhook")
def receive_alertmanager_webhook(payload: AlertmanagerPayload):
    created = 0
    updated = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            for alert in payload.alerts:
                fingerprint = alert.fingerprint

                if alert.status == "firing":
                    cur.execute(
                        """
                        INSERT INTO incidents (
                            id, fingerprint, alertname, severity,
                            status, summary, description
                        )
                        VALUES (
                            gen_random_uuid(), %s, %s, %s,
                            'open', %s, %s
                        )
                        ON CONFLICT (fingerprint)
                        DO UPDATE SET
                            status = 'open',
                            resolved_at = NULL
                        WHERE incidents.status = 'resolved'
                        RETURNING (xmax = 0) AS inserted
                        """,
                        (
                            fingerprint,
                            alert.labels.get("alertname", "Unknown"),
                            alert.labels.get("severity", "unknown"),
                            alert.annotations.get("summary", ""),
                            alert.annotations.get("description", ""),
                        ),
                    )
                    result = cur.fetchone()
                    if result:
                        if result["inserted"]:
                            created += 1
                        else:
                            updated += 1

                else:
                    cur.execute(
                        """
                        UPDATE incidents
                        SET status = 'resolved',
                            resolved_at = NOW()
                        WHERE fingerprint = %s
                          AND status = 'open'
                        """,
                        (fingerprint,),
                    )
                    updated += cur.rowcount

            cur.execute("SELECT COUNT(*) AS total FROM incidents")
            total = cur.fetchone()["total"]

    logger.info(
        f"Alertmanager webhook processed: created={created}, updated={updated}"
    )

    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "total_incidents": total,
    }


@app.get("/api/incidents")
def list_incidents():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, fingerprint, alertname, severity,
                       status, summary, description,
                       created_at, resolved_at
                FROM incidents
                ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()

    return {
        "total": len(rows),
        "incidents": rows,
    }



# ==================================================
# 11. AI INCIDENT ANALYSIS ENDPOINT
# ==================================================

from uuid import UUID
from urllib.error import URLError

from app.database import get_connection
from app.ai_client import analyze_incident


@app.post("/api/incidents/{incident_id}/analyze")
def analyze_saved_incident(incident_id: UUID):

    # STEP 1: PostgreSQL se incident find karo
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM incidents WHERE id = %s",
                (incident_id,)
            )
            incident = cur.fetchone()

    # STEP 2: Incident nahi mila toh 404
    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    # STEP 3: Local Ollama AI se analysis lo
    try:
        analysis = analyze_incident(incident)

    except (URLError, TimeoutError) as error:
        logger.error("Ollama connection failed: %s", error)

        raise HTTPException(
            status_code=503,
            detail="Local Ollama AI service unavailable"
        ) from error

    # STEP 4: AI report return karo
    return {
        "incident_id": str(incident_id),
        "fingerprint": incident["fingerprint"],
        "status": incident["status"],
        "analysis": analysis,
        "note": "AI suggestions are not confirmed root causes."
    }


# ==========================================
# LANGGRAPH AI INVESTIGATION ENDPOINT
# ==========================================

from psycopg import Error as DatabaseError
from app.agent_workflow import investigation_graph


@app.post("/api/incidents/{incident_id}/investigate")
def investigate_incident(incident_id: UUID):

    # Step 1: Start LangGraph workflow
    try:
        result = investigation_graph.invoke({
            "incident_id": str(incident_id)
        })

    # Step 2: Incident not found
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        ) from error

    # Step 3: Database or AI connection problem
    except (DatabaseError, OSError) as error:
        logger.exception("Investigation dependency failed")
        raise HTTPException(
            status_code=503,
            detail="Investigation dependency unavailable"
        ) from error

    # Step 4: Other workflow errors
    except Exception as error:
        logger.exception("Investigation workflow failed")
        raise HTTPException(
            status_code=500,
            detail="Investigation workflow failed"
        ) from error

    # Step 5: Return investigation report
    return {
        "incident_id": str(incident_id),
        "status": result["incident"]["status"],
        "monitoring": result["monitoring"],
        "logs": result["logs"],
        "analysis": result["analysis"],
        "note": "AI output requires human verification"
    }


# Live monitoring dashboard
from app.monitoring_api import router as monitoring_router

app.include_router(monitoring_router)


# Additional, non-destructive incident-time evidence workflow
from app.verified_investigation import router as verified_investigation_router
app.include_router(verified_investigation_router)
from app.verified_investigation import router as verified_investigation_router

app.include_router(verified_investigation_router)
