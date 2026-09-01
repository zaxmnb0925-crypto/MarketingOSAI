#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
BACKEND_ROOT="${PROJECT_ROOT}/backend"

if [ "$(id -u)" -eq 0 ]; then
    echo "STOP: clean-room regression must not run as root" >&2
    exit 1
fi

if [ ! -f "${PROJECT_ROOT}/AGENTS.md" ] || [ ! -d "${PROJECT_ROOT}/.git" ]; then
    echo "STOP: repository root could not be verified" >&2
    exit 1
fi

MODE="${1:-}"

case "$MODE" in
    no-external)
        export ENVIRONMENT=test
        export MARKETINGOS_TEST_MODE=no-external
        export DATABASE_URL="postgresql+asyncpg://test_user@127.0.0.1:1/marketingos_test_no_external"
        export REDIS_URL="redis://127.0.0.1:1/15"
        ;;
    integration)
        echo "STOP: batch integration is disabled; use the exact-file clean-room integration runner" >&2
        exit 2
        ;;
    *)
        echo "usage: $0 {no-external|integration}" >&2
        exit 2
        ;;
esac

export SECRET_KEY="test-only-synthetic-secret"
export OPENAI_API_KEY="test-only-not-a-live-key"
export OAUTH_TOKEN_ENCRYPTION_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
export API_DOCS_ENABLED=false
export REAL_PUBLISH_ENABLED=false
export META_PUBLISH_TRANSPORT_ENABLED=false
export META_PUBLISH_CANARY_MODE_ENABLED=true
export PYTHONPATH="${BACKEND_ROOT}:${BACKEND_ROOT}/tests"

cd "$BACKEND_ROOT"

python3 -c \
    'from _test_environment_guard import validate_test_environment; validate_test_environment()'

COMMON_ARGS=(
    -m pytest
    -q
    --disable-warnings
    -p _test_isolation_plugin
    -p _v013h_legacy_target_compat
)

mapfile -t TEST_FILES < <(
    find tests \
        -maxdepth 1 \
        -type f \
        -name 'test_*.py' \
        ! -name 'test_publication_reconciliation_postgres_integration.py' \
        ! -name 'test_publication_publish_http_integration.py' \
        ! -name 'test_publication_publish_normal_mode_integration.py' \
        ! -name 'test_p4_ai_accounting_postgres_integration.py' \
        ! -name 'test_p5_keyword_intelligence_postgres_integration.py' \
        ! -name 'test_p5_platform_admin_postgres_integration.py' \
        -print \
    | sort
)

if [ "${#TEST_FILES[@]}" -eq 0 ]; then
    echo "STOP: no no-external test files found" >&2
    exit 1
fi

exec python3 "${COMMON_ARGS[@]}" "${TEST_FILES[@]}"
