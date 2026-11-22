This folder defines an independent, locally isolated five-service Compose project.
No existing Docker data volume is attached directly to the new PostgreSQL instance.
Database data is transferred by pg_dump / pg_restore in the one-time migration script.
The original aiops-postgres-data named volume is left untouched for rollback.
Prometheus history is NOT migrated; this new instance starts with fresh metrics.
All published ports bind to 127.0.0.1 only.
Ollama remains a WSL host service and is accessed through host.docker.internal.
Never run docker compose down -v or docker volume prune for this project.
