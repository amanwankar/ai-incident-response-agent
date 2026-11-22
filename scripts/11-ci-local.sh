#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m compileall -q app
python -m unittest discover -s tests -p 'test_*.py' -v
npm --prefix dashboard run build
docker build -f Dockerfile.backend -t aiops-backend:local-ci .
docker build -f dashboard/Dockerfile -t aiops-dashboard:local-ci dashboard
printf '\nLocal CI checks passed. No image uploaded or cloud deployed.\n'
