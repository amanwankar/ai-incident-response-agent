#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo '=== Secret and backup git tracking checks ==='
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  tracked="$(git ls-files | grep -E '(^|/)(\.env($|\.)|backups/|.*\.pgdump$|.*\.dump$)' || true)"
  if [[ -n "$tracked" ]]; then
    echo 'FAIL: Sensitive paths appear tracked. Remove from Git index WITHOUT deleting local files:' >&2
    printf '%s\n' "$tracked" >&2
    exit 1
  fi
  echo 'PASS: No known backup / .env paths tracked.'
  git check-ignore backups/example.pgdump || true
else
  echo 'No Git repository initialized; Git tracking test skipped.'
fi

echo '=== Published Docker ports ==='
python3 - <<'PY'
import json, subprocess
names=[]
for name in ('aiops-final-dashboard-1','aiops-final-backend-1','aiops-final-postgres-1','aiops-final-prometheus-1','aiops-final-alertmanager-1'):
    done=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
    if done.returncode:
        continue
    row=json.loads(done.stdout)[0]
    ports=row.get('NetworkSettings',{}).get('Ports',{}) or {}
    for target, bindings in ports.items():
        for binding in bindings or []:
            print(name, target, '->', binding['HostIp'], binding['HostPort'])
            assert binding['HostIp'] in ('127.0.0.1', '::1'), 'Non-local service exposure detected'
    names.append(name)
print('Container bindings checked:',len(names))
PY

echo '=== Python dependency sanity (active environment) ==='
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  python -m pip check
else
  echo 'Skipping pip check; no venv activated.'
fi
printf 'Reminder: localhost-only does NOT replace authentication. Do not port-forward/publicly expose this lab.\n'
