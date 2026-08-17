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

IMPLEMENTED_AND_STATICALLY_VERIFIED: execution is injectable and argv-only; Docker inventory uses stopped-inclusive, no-truncation collection with only fixed ID, name, and three ownership-label fields; inspect collectors request restricted identity fields; listener checks use `ss` and `lsof`; provision separates create from exact-ID start; post-create failures preserve exact resources for review; sentinels use same-directory mode-0600 temporary files, fsync, and atomic rename after attestation; migration uses an allowlisted child environment; teardown requires fresh exact-ID observation, container-absence and port-close verification, and exact-path cleanup. Execute mode cannot use an arbitrary observation JSON file.

RUNTIME_NOT_YET_VERIFIED: no Docker daemon, image, PostgreSQL, Redis, Alembic migration, or integration test was used during B5F. Every real execution remains separately authorized.

## Exact Docker privilege boundary

The Python lifecycle remains the unprivileged operator process and execute mode
rejects UID 0 before Docker or resource mutation. Only reviewed Docker daemon
commands receive privilege, with the immutable argv prefix
`/usr/bin/sudo -- /usr/bin/docker <reviewed-arguments>`. The Docker-only
builder permits only `ps`, `create`, `start`, `inspect`, `stop`, and `rm`; the
executor rejects bare Docker, generic sudo targets, missing `--`, sudo options,
and arbitrary privileged executables. Absolute paths are source constants, not
environment or PATH selections, and subprocess execution remains argv-only with
`shell=False`, bounded capture, and timeout enforcement. Dry-run plans expose
the same privileged create argv used by execute mode.

The operator is intentionally not added to the Docker group: Docker socket
access is effectively broad host privilege and would bypass per-command sudo
review. Sudo Python, sudo shells, generic privileged wrappers, Docker socket
permission widening, password piping, askpass, and inherited sudo credentials
through environment flags are prohibited. Authentication failure of an exact
Docker command follows the existing fail-closed create-ambiguity or
post-create-preservation contract.

## Provision failure preservation boundary

Before Docker create, validation, collision, port, secret-generation, and exact
resource-root preconditions may abort without a Docker resource. The current
flow performs no automatic pre-create metadata cleanup and does not broaden
cleanup beyond existing exact-path operations.

A Docker create exception, timeout, or malformed result is ambiguous: absence
of a resource is not proven. It enters `CREATE_AMBIGUOUS_PRESERVE`; no lookup
or deletion by container name or run ID is attempted. Once create returns an
exact CID, the ownership boundary becomes `POST_CREATE_PRESERVE` until accepted
`READY`. Start, initial observation, storage attestation, listener, bounded
stability, StartedAt, sentinel write or validation, and post-sentinel failures
all return sanitized `PROVISION_FAILED_REVIEW_REQUIRED` and preserve the exact
container and resource-root evidence. Automatic `docker stop`, `docker rm`,
normal teardown, and metadata deletion are prohibited across this boundary.

A failed provision is not teardown authorization. Exact forensic review must
occur first; the operator must not rerun or automatically invoke normal
teardown. After accepted `READY`, normal teardown remains a separate, explicit
operation with its existing fresh identity, storage, listener, and sentinel
authorization gates.

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

The evidence model distinguishes three Docker inspection surfaces. The image's
`Config.Volumes={"/data":{}}` is declaration metadata only; it is not evidence
that an attached Docker volume exists. For a container created with `--tmpfs`,
the observed engine reports `.Mounts=[]`, while `HostConfig.Tmpfs` is the
authoritative configured-storage surface. Redis therefore requires exactly one
`/data` entry whose option set is semantically exactly `rw`, `size=67108864`,
and `mode=0700`. Option ordering is immaterial, but missing, duplicated,
unknown, or additional options and destinations fail closed. Any bind, named
volume, anonymous volume, or other row in `.Mounts` also fails closed.

Forensic inspection of the container's `/proc/.../mountinfo` confirmed that
`/data` is a runtime tmpfs. The normal lifecycle deliberately does not add a
mountinfo dependency: entering or inspecting container process namespaces
would add privilege and operational complexity. Instead, readiness, stability,
and teardown consistently re-attest the reviewed `HostConfig.Tmpfs`, `.Mounts`,
and `Config.Volumes` surfaces. Normal teardown performs this fresh attestation
before exact-ID stop/remove and never prunes Docker volumes.

Redis lifecycle `READY` means `RESOURCE_LIFECYCLE_STABLE`; it does not mean
`REDIS_APPLICATION_READINESS_PROVEN`. No `redis-cli`, `PING`, `FLUSHALL`,
or `FLUSHDB` is introduced.

### Operator sentinel metadata contract

Lifecycle metadata is created by the non-root lifecycle operator, without sudo.
Both `sentinel.json` and `observation.json` must be regular, non-symlink,
mode-0600 files whose UID and GID exactly equal the lifecycle process effective
UID and GID. Their same-directory temporary files and atomically replaced final
paths are checked against the same contract. File type, symlink, mode, and owner
checks are independent fail-closed requirements.

Docker privilege remains limited to exact reviewed
`/usr/bin/sudo -- /usr/bin/docker` commands; it is never used to create or repair
metadata. Wrongly owned metadata is preserved as forensic evidence, not fixed
with chmod, chown, ACL changes, or permission widening. A future host-specific
manifest may lock the observed operator UID/GID, but portable source never
hard-codes those host values or obtains expected ownership from file metadata,
environment, usernames, configuration, or CLI input.


When mode-0700 parent traversal requires a separately approved host-side
metadata check, an operator may use the exact read-only form
`sudo -- /usr/bin/stat -Lc '%F %a %u %g' <exact-sentinel-path>`. It must compare
the numeric owner to the host-specific non-root lifecycle operator UID/GID; it
must never reinterpret root ownership as valid, read file contents, or widen
permissions. This metadata-only host check does not change which process creates
or owns lifecycle evidence.
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
