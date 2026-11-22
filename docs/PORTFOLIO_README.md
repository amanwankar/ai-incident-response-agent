# AI Incident Response Agent

A **zero-cloud-cost, locally hosted AIOps lab** that turns Prometheus alerts into searchable PostgreSQL incidents and generates cautious, human-reviewed AI investigation reports using LangGraph and Ollama.

## Features

- FastAPI with `/api/health`, `/metrics`, `/api/incidents`, Alertmanager webhooks, and AI investigation endpoints.
- Prometheus/Alertmanager monitoring and firing/resolved incident lifecycle.
- PostgreSQL-backed incident persistence with deduplication.
- Local Ollama model (`qwen2.5:1.5b`), no paid inference API.
- Incident-time evidence querying (bounded Prometheus history and timestamped log matches), with missing-data handling.
- React + Nginx dashboard with incidents, live monitoring stats and request-traffic chart.
- Repeatable five-service Docker Compose, backup/restore and rollback strategy.
- Python unit tests, integration smoke tests, and GitHub Actions build/test workflow (no image push or cloud deploy).

## Architecture

See [`docs/ARCHITECTURE.md`](ARCHITECTURE.md). See [`docs/OPERATIONS.md`](OPERATIONS.md) for exact setup and recovery steps.

## Getting started

Requirements: WSL Ubuntu with Docker Desktop integration, a running local Ollama service and the existing source repository with `Dockerfile.backend`, React dashboard and FastAPI code.

Run the **preflight** before changing any legacy service:

```bash
bash scripts/01-preflight.sh
```

One-time migration to a separate PostgreSQL volume:

```bash
bash scripts/02-migrate-once.sh
```

Normal startup and verification:

```bash
bash scripts/05-start.sh
bash scripts/03-verify.sh
```

Local dashboard: http://127.0.0.1:5174/

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
npm --prefix dashboard run build
bash scripts/04-smoke-alert.sh
```

## Safety and limitations

Local demonstration only. No authentication is provided. Never expose to the internet without access control and a security review. AI output is a hypothesis and needs human confirmation. New Prometheus storage has no prior metric history. Don't run `docker volume prune`.

## Technologies

Python, FastAPI, PostgreSQL 18, Docker, Docker Compose, Prometheus, Alertmanager, React, TypeScript, Nginx, LangGraph, Ollama.

## Author

Add your own GitHub profile, contact details and screenshots after verifying the project on your machine.
