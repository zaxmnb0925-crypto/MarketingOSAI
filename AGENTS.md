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
- Backend tests must be launched through `scripts/run_backend_regression_cleanroom.sh`. Its `no-external` and `integration` modes must remain separate.
- Integration tests may use only disposable, loopback-bound PostgreSQL and Redis resources. They must never use shared resources.
- External provider network access is denied by default. Provider behavior must use mocks, fakes, `httpx.MockTransport`, ASGI transport, or monkeypatching unless a future network integration test receives separate approval.
- `scripts/run_backend_regression_isolated.sh` is **PRODUCTION-COUPLED — DO NOT USE FOR CLEAN-ROOM DEVELOPMENT**.
- Backend dependencies are range-bounded but not lock/hash pinned. Follow `docs/DEPENDENCY_REPRODUCIBILITY.md`; do not invent lock versions manually.
