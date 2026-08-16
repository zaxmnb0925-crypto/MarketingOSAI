# Repository Safety Policy

1. `/opt/MarketingOSAI` is Production and must never be modified directly.
2. Normal development is performed only in a Git development workspace.
3. Never add `.env` files, backups, database dumps, runtime data, private keys, credentials, or secrets to the repository.
4. Every change must pass relevant tests before it is accepted.
5. Database migrations require review and must never be executed automatically against Production.
6. Production deployments must use an immutable image digest.
7. A mutable tag such as `latest` must not be used as the Production release identity.
8. Do not build application artifacts or container images directly in Production.
9. Secrets must never appear in logs, test output, generated evidence, or Git history.
10. Every destructive operation requires separate, explicit human approval.
11. Codex must not use `sudo` by default.
12. Access to Production is limited to read-only verification unless separately and explicitly authorized.

## Clean-room testing policy

- Test processes must use `ENVIRONMENT=test`, synthetic credentials, and explicitly approved test endpoints. Production database, Redis, backend, and provider endpoints are prohibited.
- No-external backend tests use `scripts/run_backend_regression_cleanroom.sh no-external`. Batch integration mode must remain disabled.
- Integration tests run one exact allowlisted file at a time through `scripts/run_backend_integration_cleanroom.sh`, only after sentinel and fresh runtime-observation attestation passes.
- Integration resources must be disposable, loopback-bound, digest-pinned, run-scoped, and exclusively owned. Shared PostgreSQL/Redis, inherited resource URLs, `FLUSHALL`, `FLUSHDB`, broad process killing, pruning, or wildcard cleanup are prohibited.
- Resource sentinels must remain outside Git, contain no secrets, and match run ID, exact PID/container ID, labels, digest, listener, port, start time, and temporary path before migration, tests, or cleanup. Identity mismatch fails closed and preserves the resource.
- Lifecycle tooling must default to dry-run, use immutable `repository@sha256:<digest>` images, argv-list command construction, sanitized environments, runtime-only credentials, and exact-ID teardown. Docker, migration, and cleanup execution require separate approval.
- External provider network access is denied by default. Provider behavior must use mocks, fakes, `httpx.MockTransport`, ASGI transport, or monkeypatching unless a future network integration test receives separate approval.
- `scripts/run_backend_regression_isolated.sh` is **PRODUCTION-COUPLED — DO NOT USE FOR CLEAN-ROOM DEVELOPMENT**.
- Backend range inputs and committed hash-pinned lock candidates are documented in `docs/DEPENDENCY_REPRODUCIBILITY.md`; verified installs must retain `--require-hashes`.
