# MarketingOSAI

MarketingOSAI is a multi-tenant marketing content and publishing application. The repository contains a FastAPI/Python backend and a Next.js/React/TypeScript frontend, backed by PostgreSQL and Redis. Alembic provides database migration definitions, and Docker Compose describes the local service topology.

## Repository layout

- `backend/app/` — FastAPI application code, API routes, models, schemas, and services.
- `backend/tests/` — backend pytest test suite.
- `backend/alembic/` — Alembic environment and reviewed migration revisions.
- `frontend/app/` — Next.js application and server route handlers.
- `frontend/lib/` — shared frontend/server utilities.
- `frontend/tests/` — frontend contract tests.
- `scripts/` — repository maintenance and test helper scripts.
- `docs/` — project documentation and development records.
- `docker-compose.yml` and `docker-compose.override.yml` — local service definitions.

## Local development structure

The Compose topology defines PostgreSQL, Redis, backend, and frontend services on an internal network, with backend and frontend ports bound to loopback. Backend Python dependencies are declared in `backend/requirements.txt`, test dependencies in `backend/requirements-test.txt`, and frontend dependencies and scripts in `frontend/package.json`.

Start local configuration by copying `.env.example` to an untracked `.env`. Replace every secret placeholder through an approved secret manager or the deployment environment. Keep publishing disabled unless a separately reviewed environment explicitly enables it. The `.env` file must never be committed.

Backend tests are under `backend/tests/`; frontend contract tests are under `frontend/tests/`. Run the tests relevant to every change. Migration revisions are under `backend/alembic/versions/`; migrations require review and must not be applied automatically to Production.

## Security and deployment principles

Production is a read-only verification target for normal development. Do not build directly in Production, and do not store secrets, backups, database dumps, runtime data, or private keys in Git. Production releases must be identified by immutable image digests; mutable tags such as `latest` are not valid release identities. Destructive operations and Production migrations require explicit human approval.

## Version metadata

- Product production baseline: `v0.15-beta-rc1`.
- Known metadata debt: backend `APP_VERSION`/default metadata remains `0.13H`.

This is a known metadata mismatch. It does not indicate a mismatch in the current Production image and should be resolved through a later, normal version change. This repository-hardening change intentionally does not modify backend application-version metadata.
