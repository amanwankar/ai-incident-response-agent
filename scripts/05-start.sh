#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${AIOPS_DB_PASSWORD:-}" ]]; then
  read -r -s -p 'Final-stack PostgreSQL password (not stored): ' AIOPS_DB_PASSWORD
  echo
fi
export AIOPS_DB_PASSWORD
for name in aiops-final-postgres-data aiops-final-prometheus-data aiops-final-alertmanager-data; do
  docker volume inspect "$name" >/dev/null || { echo "Volume $name missing. Run one-time migration first." >&2; exit 1; }
done
docker compose -f deploy/compose.final.yaml up -d --build
bash scripts/03-verify.sh
