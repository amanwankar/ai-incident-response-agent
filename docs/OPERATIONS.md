# Operations runbook (WSL2 / Docker Desktop)

## One-time install and migration

```bash
cd ~/projects/ai-incident-response-agent
bash /path/to/aiops_finish_kit/setup.sh "$PWD"
bash scripts/01-preflight.sh
bash scripts/02-migrate-once.sh
```

The migration has guardrails, validates the PostgreSQL 18 named-volume mount,
creates a logical `pg_dump -Fc` backup, stops the *old* AIOps containers
without removing them, restores into an independent external volume, and
compares incident counts before starting the full five-service stack.
It requires typing `MIGRATE`. Never rerun the migration against an existing
`aiops-final-postgres-data` volume.

## Daily start

```bash
cd ~/projects/ai-incident-response-agent
bash scripts/05-start.sh
```

Ollama is a separate WSL service and must be running (`curl http://127.0.0.1:11434/api/version`).
When the terminal asks for the database password, it does not echo or save it.

## Daily stop / restore old stack

```bash
bash scripts/06-stop.sh
bash scripts/07-rollback-legacy.sh  # only if you need to restore original old containers
```

`compose down` does not delete data volumes; volumes are declared external.
Never use `docker volume prune`, `docker system prune --volumes` or manually
remove `aiops-postgres-data`. Keep the backup archive offline/private.

## Health checks

```bash
bash scripts/03-verify.sh
bash scripts/04-smoke-alert.sh
bash scripts/08-restart-test.sh
curl -fsS http://127.0.0.1:5174/api/incidents | python3 -m json.tool
curl -fsS http://127.0.0.1:8001/api/monitoring | python3 -m json.tool
```

## Logs

```bash
docker compose -f deploy/compose.final.yaml ps
docker compose -f deploy/compose.final.yaml logs --tail=100 backend
docker compose -f deploy/compose.final.yaml logs --tail=100 alertmanager
docker compose -f deploy/compose.final.yaml logs --tail=100 prometheus
```

## Known limitations / troubleshooting

- `fastapi_up: 1.0` means Prometheus successfully scraped the configured target, not that all APIs are functional.
- `http_5xx...: null` means the metric wasn't returned; it DOES NOT mean zero errors.
- `HTTP 404 /investigate-verified`: check router registration in app/main.py, rebuild backend.
- `AI status skipped`: no relevant incident-time evidence available; don't invent an RCA.
- `AI status unavailable`: check WSL Ollama `curl http://127.0.0.1:11434/api/version` and container access to host.docker.internal:11434.
- `Address already in use`: old containers or WSL Uvicorn may still own the port; identify with `ss -lntp`, `docker ps` before stopping any process.
- After migration, old Prometheus metrics do not automatically appear in the new Prometheus data volume.
- The `logs/fastapi.log` bind mount captures old host-generated logs. Container stdout logs are visible via `docker compose logs` but do not automatically populate the mounted file. Thus missing timestamped log evidence is normal until centralized logging is implemented.
