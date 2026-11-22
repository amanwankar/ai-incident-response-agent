#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${AIOPS_DB_PASSWORD:-}" ]]; then
  read -r -s -p 'Original PostgreSQL password: ' AIOPS_DB_PASSWORD
  echo
fi
export AIOPS_DB_PASSWORD
printf 'This stops the FINAL stack and restarts your preserved LEGACY containers.\n'
read -r -p 'Type ROLLBACK to proceed: ' answer
[[ "$answer" == ROLLBACK ]] || { echo 'Canceled'; exit 0; }
docker compose -f deploy/compose.final.yaml down
docker start aiops-postgres prometheus alertmanager
docker compose -f compose.backend.yaml -f compose.fullstack.yaml up -d --no-build
printf 'Legacy services restarted; original aiops-postgres-data was never overwritten.\n'
