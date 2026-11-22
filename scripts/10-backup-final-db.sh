#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${AIOPS_DB_PASSWORD:-}" ]]; then
  read -r -s -p 'PostgreSQL password: ' AIOPS_DB_PASSWORD; echo
fi
export AIOPS_DB_PASSWORD
mkdir -p backups
chmod 700 backups
umask 077
backup="backups/final-incident_db-$(date -u +%Y%m%d-%H%M%S).pgdump"
docker compose -f deploy/compose.final.yaml exec -T postgres pg_dump -U aiops -d incident_db -Fc > "$backup"
test -s "$backup"
docker compose -f deploy/compose.final.yaml exec -T postgres pg_restore -l < "$backup" >/dev/null
printf 'Verified database backup: %s (%s bytes)\n' "$backup" "$(wc -c < "$backup")"
