# Portfolio demonstration — 5-minute walkthrough

1. **Startup**: `bash scripts/05-start.sh`, show five running Compose services.
2. **Dashboard**: visit http://127.0.0.1:5174/, show incident counts and traffic chart.
3. **Monitoring**: visit http://127.0.0.1:9090/targets and verify backend target UP.
4. **Synthetic alert**: run `bash scripts/04-smoke-alert.sh` and show warning incident firing/resolved transitions.
5. **AI**: click the dashboard investigation button. For historic incidents, model should report insufficient incident-time evidence rather than inventing a root cause.
6. **Persistence**: restart backend, recheck incidents and data persistence.
7. **CI**: show Python tests, React build and Docker builds in GitHub Actions after explicitly enabling a public-repo workflow.

## What I built (resume-ready, verify your actual repository state first)

**AI Incident Response Agent** — Designed and implemented a local, containerized AIOps system using FastAPI, LangGraph, Ollama, PostgreSQL, Prometheus, Alertmanager, Docker Compose, and React. Developed alert-to-incident persistence, metrics dashboards, human-reviewed AI investigation, cautious incident-time evidence collection, backup/rollback workflows and CI checks.

## Demonstration claims to avoid

- Do NOT say that the AI automatically fixes incidents.
- Do NOT say that an AI-generated possible root cause has been confirmed.
- Do NOT say the new Prometheus holds the old historical TSDB data.
- Do NOT say this setup has full authentication, HA, disaster recovery or production-grade security.
