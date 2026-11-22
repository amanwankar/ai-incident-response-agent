#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo '=== Local tools ==='
command -v docker
command -v python3
docker compose version
docker info --format 'Docker server: {{.ServerVersion}}'

echo '=== Verify ORIGINAL Postgres storage (read-only) ==='
python3 - <<'PY'
import json, subprocess
row=json.loads(subprocess.check_output(['docker','inspect','aiops-postgres'], text=True))[0]
mounts=[(x.get('Name'),x.get('Destination')) for x in row['Mounts']]
print('Image:',row['Config']['Image'])
print('Mounts:',mounts)
assert ('aiops-postgres-data','/var/lib/postgresql') in mounts, 'Unexpected Postgres volume/mount; STOP and inspect'
assert row['Config']['Image'].startswith('postgres:18'), 'Expected postgres:18; STOP and inspect'
PY

docker exec aiops-postgres psql -U aiops -d incident_db -Atc 'SHOW server_version;'
docker exec aiops-postgres psql -U aiops -d incident_db -Atc 'SELECT count(*) FROM incidents;'

echo '=== Current containers (read-only) ==='
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo '=== Existing alert config ==='
test -f monitoring/alertmanager/alertmanager.yml
grep -nE 'receiver:|url:|send_resolved:' monitoring/alertmanager/alertmanager.yml || true

echo '=== Existing application files ==='
for path in Dockerfile.backend dashboard/Dockerfile dashboard/nginx.conf requirements.txt deploy/compose.final.yaml; do
  test -f "$path" || { echo "Missing: $path"; exit 1; }
done
if ! grep -q 'proxy_pass http://backend:8000' dashboard/nginx.conf; then
  echo 'STOP: dashboard/nginx.conf must proxy_pass http://backend:8000'
  exit 1
fi

if docker volume inspect aiops-final-postgres-data >/dev/null 2>&1; then
  echo 'NOTICE: final database volume already exists. One-time migration must NOT be rerun.'
else
  echo 'Final stack will use a NEW independent database volume.'
fi

echo 'Preflight checks complete; nothing stopped or modified.'
