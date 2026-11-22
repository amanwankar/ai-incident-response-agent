
import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen


PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://127.0.0.1:9090"
)


def query_prometheus(query):
    # Step 1: Prometheus query URL banao
    params = urlencode({"query": query})
    url = f"{PROMETHEUS_URL}/api/v1/query?{params}"

    # Step 2: Prometheus se response lo
    with urlopen(url, timeout=10) as response:
        data = json.load(response)

    # Step 3: Response validate karo
    if data.get("status") != "success":
        raise ValueError("Prometheus query failed")

    results = data["data"]["result"]

    # Data missing ho toh None return karo
    if not results:
        return None

    # Step 4: Metric ki numeric value return karo
    return float(results[0]["value"][1])


def get_monitoring_evidence():

    # FastAPI scrape status
    fastapi_up = query_prometheus(
        'up{job="fastapi"}'
    )

    # Last 5 minutes ke HTTP 5xx errors
    error_count = query_prometheus(
        'sum(increase(http_server_errors_total{job="fastapi"}[5m]))'
    )

    return {
        "fastapi_up": fastapi_up,
        "http_5xx_last_5m_estimate": error_count,
    }
