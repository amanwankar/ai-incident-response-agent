#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${AIOPS_DB_PASSWORD:-}" ]]; then
  read -r -s -p 'Final-stack PostgreSQL password: ' AIOPS_DB_PASSWORD
  echo
fi
export AIOPS_DB_PASSWORD
docker compose -f deploy/compose.final.yaml down
printf 'Compose containers stopped/removed; external volumes kept. NEVER run volume prune.\n'
