# Dependency Reproducibility Policy

## Current state

Backend runtime dependencies in `backend/requirements.txt` use bounded version ranges, while direct test runner dependencies in `backend/requirements-test.txt` are exact. These two files remain the authoritative resolver inputs.

Python 3.12 lock candidates are stored in `backend/requirements.lock` and `backend/requirements-test.lock`. They contain exact transitive versions and artifact hashes, omit index configuration, and were generated with pip-tools 7.6.0 using its backtracking resolver. The test lock derives from both authoritative inputs and is verified in a second clean environment with pip `--require-hashes`.

The frontend uses npm lockfile version 3. `frontend/package.json` and the root package metadata in `frontend/package-lock.json` agree. `npm ci` is the intended clean installation mechanism when dependency installation is separately authorized.

## Proposed backend locking procedure

1. Start from the immutable, reviewed input files `backend/requirements.txt` and `backend/requirements-test.txt`.
2. Use a clean, isolated Python 3.12 environment on the supported target platform.
3. Resolve dependencies with a separately approved resolver and package-index network session. Do not resolve on Production.
4. Generate separate exact, hash-pinned runtime and test lock files from the reviewed inputs.
5. Record the Python version, platform, resolver name/version, index identity, input file hashes, and generation command.
6. Review the complete transitive dependency diff, licenses, advisories, unexpected indexes, direct URLs, and source distributions.
7. Verify installation using hashes in a second clean environment with no fallback to unpinned packages.
8. Run the no-external test group with outbound network denied, then run integration tests only against disposable resources.
9. Commit input changes and generated locks together only after review and successful verification.

No exact backend versions are selected by this document. Lock generation requires a separately authorized resolver/network operation.
