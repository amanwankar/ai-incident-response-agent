
import json
import os
import time

from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException

from app.metrics_client import (
    get_monitoring_evidence,
    query_prometheus,
)


router = APIRouter()

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://127.0.0.1:9090"
).rstrip("/")


def get_request_history():
    # Last 30 minutes
    end = int(time.time())
    start = end - 1800

    query = (
        'sum(rate(http_requests_total'
        '{job="fastapi"}[2m])) * 60'
    )

    params = urlencode({
        "query": query,
        "start": start,
        "end": end,
        "step": 30
    })

    url = (
        f"{PROMETHEUS_URL}/api/v1/query_range"
        f"?{params}"
    )

    with urlopen(url, timeout=10) as response:
        payload = json.load(response)

    if payload.get("status") != "success":
        raise ValueError("Prometheus query failed")

    results = payload["data"]["result"]

    if not results:
        return []

    history = []

    for timestamp, value in results[0]["values"]:
        history.append({
            "timestamp": float(timestamp),
            "requests_per_minute": round(
                float(value), 2
            )
        })

    return history


@router.get("/api/monitoring")
def get_monitoring():

    try:
        # Existing metrics client
        evidence = get_monitoring_evidence()

        # Current request rate
        request_rate = query_prometheus(
            'sum(rate(http_requests_total'
            '{job="fastapi"}[2m])) * 60'
        )

        # Historical traffic points
        history = get_request_history()

    except (
        OSError,
        ValueError,
        KeyError,
        TypeError
    ) as error:
        raise HTTPException(
            status_code=503,
            detail="Prometheus metrics unavailable"
        ) from error

    return {
        "collected_at": time.time(),
        "fastapi_up": evidence["fastapi_up"],
        "http_5xx_last_5m_estimate": evidence[
            "http_5xx_last_5m_estimate"
        ],
        "request_rate_per_minute": request_rate,
        "history": history
    }
