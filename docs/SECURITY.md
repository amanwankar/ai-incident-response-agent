# Security and reliability checklist

- [x] Intended for LOCALHOST ONLY; Compose binds published ports to 127.0.0.1.
- [x] DB password is provided interactively as an environment variable, not saved in repo or workflow.
- [x] Backups folder and `logs/` are gitignored by setup script; backup directory permissions 0700.
- [x] Docker volumes for the FINAL stack are external, avoiding deletion by Compose down.
- [x] No automatic remediation, shell execution from model text, or privileged Docker container access.
- [x] GitHub workflow has `contents: read` permission and never pushes images.
- [ ] Add authentication/RBAC and audit logs before exposing API to untrusted users.
- [ ] Move secrets into a proper secrets manager before any multi-user production deployment.
- [ ] Pin Docker image digests and GitHub Action SHAs for production-grade supply-chain assurance.
- [ ] Add dependency vulnerability scans and SAST after baseline builds/tests pass.
- [ ] Add log aggregation with reliable timestamped correlation (current host-mounted file is limited).
- [ ] Document RPO/RTO and rehearse full DB backup restore before treating this as production-ready.
- [ ] Avoid running the Ollama service on public interfaces.

No billing is expected for local Docker/WSL/Ollama. GitHub Actions standard runners
in public repositories are currently free, but private repository quotas or
other paid runner/service choices may cause usage charges. Check settings before enabling.
