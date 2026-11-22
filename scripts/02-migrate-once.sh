#!/usr/bin/env bash
# One-time, guarded cutover. NEVER removes original DB containers/volumes.
set -euo pipefail
cd "$(dirname "$0")/.."
FILE=deploy/compose.final.yaml
OLD=(docker compose -f compose.backend.yaml -f compose.fullstack.yaml)
NEW=(docker compose -f "$FILE")
cutover=0

rollback_on_error() {
  local status=$?
  trap - EXIT
  if (( status != 0 && cutover == 1 )); then
    echo 'ERROR after cutover; stopping new stack and restarting originals.' >&2
    "${NEW[@]}" down || true
    docker start aiops-postgres prometheus alertmanager || true
    "${OLD[@]}" up -d --no-build || true
    echo 'Original Postgres volume was NOT modified.' >&2
  fi
  exit "$status"
}
trap rollback_on_error EXIT

bash scripts/01-preflight.sh
if docker volume inspect aiops-final-postgres-data >/dev/null 2>&1; then
  echo 'STOP: destination database volume already exists. Use scripts/05-start.sh instead.' >&2
  exit 1
fi

if [[ -z "${AIOPS_DB_PASSWORD:-}" ]]; then
  read -r -s -p 'Existing PostgreSQL password (not echoed or saved): ' AIOPS_DB_PASSWORD
  echo
fi
export AIOPS_DB_PASSWORD
"${NEW[@]}" config -q

mkdir -p backups
chmod 700 backups
BACKUP="backups/incident_db-$(date -u +%Y%m%d-%H%M%S).pgdump"
umask 077

echo 'Taking a FIRST live backup before stopping anything...'
docker exec aiops-postgres pg_dump -U aiops -d incident_db -Fc > "$BACKUP"
test -s "$BACKUP"
docker exec -i aiops-postgres pg_restore -l < "$BACKUP" >/dev/null
printf 'Backup validated: %s (%s bytes)\n' "$BACKUP" "$(wc -c < "$BACKUP")"
printf '\nThis will STOP (not remove) the existing AIOps containers and start a fresh five-service Compose stack.\n'
printf 'The old aiops-postgres-data volume and original containers will remain for rollback.\n'
read -r -p 'Type MIGRATE to proceed: ' CONFIRM
[[ "$CONFIRM" == 'MIGRATE' ]] || { echo 'Canceled without stopping containers.'; exit 0; }

cutover=1
"${OLD[@]}" stop
# Stop Alertmanager first so no new webhook writes occur during final DB snapshot.
docker stop alertmanager
# Final consistent snapshot after old backend and alertmanager are stopped.
docker exec aiops-postgres pg_dump -U aiops -d incident_db -Fc > "$BACKUP"
test -s "$BACKUP"
docker exec -i aiops-postgres pg_restore -l < "$BACKUP" >/dev/null
ORIGINAL_COUNT="$(docker exec aiops-postgres psql -U aiops -d incident_db -Atc 'SELECT count(*) FROM incidents;')"
docker stop prometheus aiops-postgres

# External named volumes are immune to compose down -v (though NEVER use prune).
docker volume create aiops-final-postgres-data >/dev/null
docker volume create aiops-final-prometheus-data >/dev/null
docker volume create aiops-final-alertmanager-data >/dev/null

"${NEW[@]}" up -d postgres
# Wait up to 75 seconds, checking Docker's PG health.
READY=0
for attempt in $(seq 1 25); do
  if "${NEW[@]}" exec -T postgres pg_isready -U aiops -d incident_db >/dev/null 2>&1; then READY=1; break; fi
  sleep 3
done
[[ "$READY" == 1 ]] || { echo 'New Postgres did not become ready' >&2; exit 1; }

# New destination database is empty; do not overwrite an existing populated DB.
EXISTING_TABLE="$("${NEW[@]}" exec -T postgres psql -U aiops -d incident_db -Atc "SELECT to_regclass('public.incidents') IS NOT NULL;")"
[[ "$EXISTING_TABLE" == 'f' ]] || { echo 'New database already has incidents table. Refusing restore.' >&2; exit 1; }
"${NEW[@]}" exec -T postgres pg_restore -U aiops -d incident_db --no-owner --no-acl < "$BACKUP"
NEW_COUNT="$("${NEW[@]}" exec -T postgres psql -U aiops -d incident_db -Atc 'SELECT count(*) FROM incidents;')"
[[ "$NEW_COUNT" == "$ORIGINAL_COUNT" ]] || { echo "Incident count differs: original=$ORIGINAL_COUNT new=$NEW_COUNT" >&2; exit 1; }
echo "Restore verified: $NEW_COUNT incidents match the original database."

"${NEW[@]}" up -d --build
bash scripts/03-verify.sh
cutover=0
printf '\nMIGRATION SUCCESS. Old containers are stopped, NOT removed.\nOriginal DB volume: aiops-postgres-data (untouched).\nBackup: %s\n' "$BACKUP"
