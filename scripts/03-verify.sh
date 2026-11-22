#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
FILE=deploy/compose.final.yaml

echo '=== Five-service Compose status ==='
docker compose -f "$FILE" ps

echo "=== Ensure final stack is running ==="
RUNNING="$(docker compose -f "$FILE" ps --services --status running)"

for service in postgres backend prometheus alertmanager dashboard; do
  if ! grep -qx "$service" <<< "$RUNNING"; then
    echo "ERROR: Final service $service is not running." >&2
    exit 1
  fi
done

echo "All five final services are running."

echo '=== HTTP tests ==='
for item in '8001/api/health' '5174/' '5174/api/incidents' '5174/api/monitoring'; do
  curl -fsS -o /dev/null -w "$item HTTP %{http_code}\n" "http://127.0.0.1:$item"
done

echo '=== Incidents and monitoring ==='
curl -fsS http://127.0.0.1:5174/api/incidents | python3 -c 'import json,sys; d=json.load(sys.stdin); print("Stored incidents:", d.get("total")); print("Alerts:", [x["alertname"] for x in d.get("incidents",[])])'
curl -fsS http://127.0.0.1:5174/api/monitoring | python3 -c 'import json,sys; d=json.load(sys.stdin); print("FastAPI scrape:",d.get("fastapi_up")); print("Traffic points:",len(d.get("history",[])))'

echo '=== New incident-time evidence endpoint ==='
curl -fsS -o /dev/null -w 'OpenAPI HTTP %{http_code}\n' http://127.0.0.1:8001/openapi.json
python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8001/openapi.json',timeout=10) as response:
    doc=json.load(response)
print('Evidence-gated endpoint registered:', any('/investigate-verified' in x for x in doc['paths']))
assert any('/investigate-verified' in x for x in doc['paths']), 'New AI route is not registered'
PY

echo '=== Prometheus target checks ==='
python3 - <<'PY'
import json,urllib.request
with urllib.request.urlopen('http://127.0.0.1:9090/api/v1/targets',timeout=10) as r:
    doc=json.load(r)
for item in doc['data'].get('activeTargets',[]):
    if item.get('labels',{}).get('job')=='fastapi':
        print('fastapi scrapeUrl:',item.get('scrapeUrl'),'health:',item.get('health'))
PY

echo '=== Alertmanager configuration ==='

docker compose -f "$FILE" exec -T alertmanager \
  amtool check-config /etc/alertmanager/alertmanager.yml

docker compose -f "$FILE" exec -T alertmanager \
  grep -Fq 'http://backend:8000/api/alerts/webhook' \
  /etc/alertmanager/alertmanager.yml

echo 'Mounted Docker backend webhook: PASS'

curl -fsS -o /dev/null \
  -w 'Alertmanager readiness HTTP %{http_code}\n' \
  http://127.0.0.1:9093/-/ready

echo 'CHECKS COMPLETE. Curl 200 confirms API reachability, not AI correctness.'
