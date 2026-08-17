# Disposable integration resource safety

Integration tests are prohibited from using shared or Production resources. Each run must use a strict `r22-<16 lowercase hex>` run ID and independently attested PostgreSQL and, when required, Redis resources. Sentinel and runtime-observation JSON files live below `/tmp/marketingos-integration-resources/<run-id>/<resource-type>/`, outside the repository. Directories are mode `0700`; files are mode `0600`; symlinks and paths outside the approved root fail closed. Sentinels never contain passwords, tokens, keys, or credential-bearing URLs.

Docker-backed resources require immutable image digests, exact container IDs, loopback-only published high ports, and these labels:

- `com.marketingos.test-resource=true`
- `com.marketingos.test-run-id=<run-id>`
- `com.marketingos.test-resource-type=postgres|redis`

Container name alone is not ownership evidence. Pre-start `ss` and `lsof` checks reduce collision risk but do not eliminate races; a fresh post-start observation must match the sentinel, listener, labels, identity, digest, port, start time, and temporary directory before migration or tests. Cleanup repeats the same validation. Mismatch preserves the resource for human review—never use broad process killing, pruning, wildcard deletion, `FLUSHALL`, or `FLUSHDB`.

PostgreSQL database and user names are derived from the run ID. `DATABASE_URL` is reconstructed in process memory from attested fields plus a runtime-only synthetic password. Redis uses an attested dedicated resource, non-default loopback port, and non-zero DB; `REDIS_URL` is likewise reconstructed. Arbitrary inherited URLs are unset. Schema bootstrap may target only Alembic source head `7c91e2f4b6a8` after the migration gate passes.

The first integration entry point accepts exactly one of:

- `backend/tests/test_publication_reconciliation_postgres_integration.py` (PostgreSQL)
- `backend/tests/test_publication_publish_http_integration.py` (PostgreSQL and Redis)
- `backend/tests/test_publication_publish_normal_mode_integration.py` (PostgreSQL and Redis)

Test fixture identities are derived from `TEST_RUN_ID`; publish tests select only their exact run-owned social account. Redis confirmation and activation keys are tracked and deleted individually, while teardown of the dedicated Redis resource remains the final isolation boundary. This policy documents safety tooling only: no disposable Docker resource, migration, or integration execution has yet been verified.

## Lifecycle tooling status

The provision, observation, migration, and teardown CLIs are default-dry-run and statically verified. Image references must use `repository@sha256:<64 lowercase hex>`; tag-only references are rejected. Docker specifications use argv lists, explicit loopback publishing, required ownership labels, bridge networking, and no Production mount or network. PostgreSQL passwords remain runtime-only and never enter sentinel JSON or sanitized plans.

Supplied Docker observations must attest the exact container ID, digest, labels, derived name, running state, host/internal ports, start time, mounts, and bridge network. Migration authorization reconstructs the target in memory and fixes the source head at `7c91e2f4b6a8`. Teardown authorization produces commands only for the exact attested container ID and validates the exact run/resource cleanup directory. Any mismatch reports no authorization and preserves the resource.

The only permitted lifecycle order is provision → observe → attest → migrate PostgreSQL → one exact allowlisted integration file → verify → exact teardown. Actual Docker execution, resource creation, Alembic execution, and integration tests remain unapproved and have not occurred.

## B5F execute-mode status

IMPLEMENTED_AND_STATICALLY_VERIFIED: execution is injectable and argv-only; Docker inventory and inspect collectors request restricted identity fields; listener checks use `ss` and `lsof`; provision separates create from exact-ID start; provisional rollback re-observes ownership; sentinels use same-directory mode-0600 temporary files, fsync, and atomic rename after attestation; migration uses an allowlisted child environment; teardown requires fresh exact-ID observation, container-absence and port-close verification, and exact-path cleanup. Execute mode cannot use an arbitrary observation JSON file.

RUNTIME_NOT_YET_VERIFIED: no Docker daemon, image, PostgreSQL, Redis, Alembic migration, or integration test was used during B5F. Every real execution remains separately authorized.

B5E candidate inputs were resolved on 2026-08-16 for linux/amd64 and have not been pulled or daemon-verified. Revalidate them before future execution when policy requires:

- `docker.io/library/postgres@sha256:075f7ba66bc9b3ce7d6b8b635208ff61cd7cf1a67d71ec530eec5d7ae0cbe571`
- `docker.io/library/redis@sha256:9702d01c1f10c3ea9f48211b4362e44f154ff02d063e6f7268eba804059f53bf`
