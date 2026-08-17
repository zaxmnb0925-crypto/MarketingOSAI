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

The provision, observation, migration, and teardown CLIs are default-dry-run and statically verified. Image references must use `repository@sha256:<64 lowercase hex>`; tag-only references are rejected. Docker specifications use argv lists, explicit loopback publishing, required ownership labels, bridge networking, and no Production mount or network. PostgreSQL provisioning generates a 256-bit synthetic secret inside the execute process. External PostgreSQL secret variables are rejected; the generated value exists only in the fixed Docker child environment and never enters argv, sentinel JSON, diagnostics, or sanitized plans.

Supplied Docker observations must attest the exact container ID, digest, labels, derived name, running state, host/internal ports, start time, mounts, and bridge network. Migration authorization reconstructs the target in memory and fixes the source head at `7c91e2f4b6a8`. Teardown authorization produces commands only for the exact attested container ID and validates the exact run/resource cleanup directory. Any mismatch reports no authorization and preserves the resource.

The only permitted lifecycle order is provision → observe → attest → migrate PostgreSQL → one exact allowlisted integration file → verify → exact teardown. Actual Docker execution, resource creation, Alembic execution, and integration tests remain unapproved and have not occurred.

## B5F execute-mode status

IMPLEMENTED_AND_STATICALLY_VERIFIED: execution is injectable and argv-only; Docker inventory uses stopped-inclusive, no-truncation collection with only fixed ID, name, and three ownership-label fields; inspect collectors request restricted identity fields; listener checks use `ss` and `lsof`; provision separates create from exact-ID start; provisional rollback re-observes ownership; sentinels use same-directory mode-0600 temporary files, fsync, and atomic rename after attestation; migration uses an allowlisted child environment; teardown requires fresh exact-ID observation, container-absence and port-close verification, and exact-path cleanup. Execute mode cannot use an arbitrary observation JSON file.

RUNTIME_NOT_YET_VERIFIED: no Docker daemon, image, PostgreSQL, Redis, Alembic migration, or integration test was used during B5F. Every real execution remains separately authorized.

B5E candidate inputs were resolved on 2026-08-16 for linux/amd64 and have not been pulled or daemon-verified. Revalidate them before future execution when policy requires:

- `docker.io/library/postgres@sha256:075f7ba66bc9b3ce7d6b8b635208ff61cd7cf1a67d71ec530eec5d7ae0cbe571`
- `docker.io/library/redis@sha256:9702d01c1f10c3ea9f48211b4362e44f154ff02d063e6f7268eba804059f53bf`

## Operator manifest invalidation

Operator lifecycle manifests are single-source-state review artifacts. Any HEAD, tree, working-tree, or participating source-hash mismatch makes the manifest `STALE_DO_NOT_EXECUTE`; it must not be updated in place or executed. The B5I manifest for run `r22-0a185d9a8efd9241` became stale when B5J lifecycle sources changed and must be regenerated only in a separately approved round.

## Dedicated PostgreSQL data layout and lifecycle stability

For every new PostgreSQL lifecycle, the resource root is
`/tmp/marketingos-integration-resources/<run-id>/postgres/`; lifecycle metadata
(`observation.json`, `sentinel.json`, and their atomic-write temporary files)
stays in that root. The only bind source permitted for container destination
`/var/lib/postgresql/data` is the dedicated `postgres/data/` child. Immediately
before Docker create, that exact child must be a non-symlink directory beneath
the validated resource root and contain no entries, including hidden entries.
Unexpected contents are preserved and fail closed as `PGDATA_NOT_EMPTY`.

Provisioning requires a two-second monotonic stability window, polled every
0.5 seconds. Every fresh restricted observation must retain exact container ID,
name, immutable digest, ownership labels, run ID, resource type, StartedAt,
running state, loopback listener, ports, mount, and network. Tests inject a fake
clock and sleeper. After the sentinel atomic rename, one more fresh restricted
observation and listener attestation is mandatory before `READY`.

`READY` means `RESOURCE_LIFECYCLE_STABLE`; it does not mean
`POSTGRESQL_APPLICATION_READINESS_PROVEN`. This lifecycle gate performs no
`psql`, authenticated SQL query, or `docker exec`. Application readiness needs
a separately reviewed design.

Normal teardown remains exact-ID and fresh-observation based. It requires the
owned container to be running and its expected listener to be present. It does
not accept an exited container or a closed expected port.

## Redis ephemeral /data storage

Real-Docker inspection established that the approved official Redis image
declares `VOLUME /data`. Without an explicit override Docker may silently
allocate an anonymous local volume. Disposable test Redis therefore mounts
exactly one controlled tmpfs at `/data` using
`--tmpfs /data:rw,size=67108864,mode=0700`. This 64 MiB, mode-0700,
read-write tmpfs is container-lifetime storage: no bind source, named volume,
anonymous volume, or persistent host data path is authorized. RDB and AOF
remain disabled.

Restricted runtime observations retain mount type, source, destination, and
read/write state. Redis accepts only the exact tmpfs identity above; a volume,
bind, wrong destination, duplicate, or additional mount fails closed and is
preserved for forensic review. Normal teardown repeats this fresh storage
attestation before exact-ID stop/remove and never prunes Docker volumes.

Redis lifecycle `READY` means `RESOURCE_LIFECYCLE_STABLE`; it does not mean
`REDIS_APPLICATION_READINESS_PROVEN`. No `redis-cli`, `PING`, `FLUSHALL`,
or `FLUSHDB` is introduced.

### Operator sentinel metadata contract

When root-owned mode-0700 parents prevent nonprivileged traversal, future
operator materialization must inspect only the exact sentinel metadata using a
separately approved command semantically equivalent to
`sudo -- /usr/bin/stat -Lc '%F %a %U %G' <exact-sentinel-path>`. Authorization
requires a regular, non-symlink, root-owned mode-0600 file. Never display its
contents and never work around visibility with permission, ownership, group, or
ACL widening.

### Preserved legacy resource recovery specification (design only)

The failed legacy run `r22-06ec72c39b79fc04` is not reinterpreted or migrated
to the new layout. No `data/` child may be created beneath it. Recovery remains
unauthorized until a separate human-approved procedure freshly proves all of:
exact CID `d2b972008bc3cd6b6d0c22287a44438dc6541f2e34811edb8ff6f0ba1f362047`;
exact name `marketingos-r22-06ec72c39b79fc04-postgres`; exact run ID and
`test-resource=true`, resource type `postgres`; image digest
`sha256:075f7ba66bc9b3ce7d6b8b635208ff61cd7cf1a67d71ec530eec5d7ae0cbe571`;
state exited; port 55432 closed; exact regular root-owned mode-0600 sentinel;
legacy mount source equal to the resource root and destination
`/var/lib/postgresql/data`; and only expected non-Production network semantics.
Any recovery must be exact-ID only: no fuzzy/name-only deletion, prune,
Production resource access, or arbitrary-path deletion.
