#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
FILE=deploy/compose.final.yaml
if [[ -z "${AIOPS_DB_PASSWORD:-}" ]]; then
  read -r -s -p 'PostgreSQL password: ' AIOPS_DB_PASSWORD; echo
fi
export AIOPS_DB_PASSWORD
BEFORE="$(curl -fsS http://127.0.0.1:5174/api/incidents | python3 -c 'import json,sys;print(json.load(sys.stdin)["total"])')"
read -r -p 'This restarts ONLY the backend (may trigger FastAPIDown test alerts). Type RESTART: ' confirm
[[ "$confirm" == RESTART ]] || { echo Canceled; exit 0; }
docker compose -f "$FILE" restart backend
READY=0
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:5174/api/health >/dev/null 2>&1; then READY=1; break; fi
  sleep 3
done
[[ "$READY" == 1 ]] || { echo 'Backend not healthy after restart' >&2; exit 1; }
AFTER="$(curl -fsS http://127.0.0.1:5174/api/incidents | python3 -c 'import json,sys;print(json.load(sys.stdin)["total"])')"
printf 'Backend recovered. Incidents before: %s, after: %s (may rise if alert triggered).\n' "$BEFORE" "$AFTER"
