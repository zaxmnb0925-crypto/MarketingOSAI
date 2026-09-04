#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
BACKEND_ROOT="${PROJECT_ROOT}/backend"

if [ "$#" -ne 1 ]; then
    echo "usage: $0 <exact-allowlisted-integration-file>" >&2
    exit 2
fi

case "$1" in
    backend/tests/test_p4_ai_accounting_postgres_integration.py) NEED_REDIS=false ;;
    backend/tests/test_p5_platform_admin_postgres_integration.py) NEED_REDIS=false ;;
    backend/tests/test_p5_keyword_intelligence_postgres_integration.py) NEED_REDIS=false ;;
    backend/tests/test_publication_reconciliation_postgres_integration.py) NEED_REDIS=false ;;
    backend/tests/test_publication_publish_http_integration.py) NEED_REDIS=true ;;
    backend/tests/test_publication_publish_normal_mode_integration.py) NEED_REDIS=true ;;
    *) echo "STOP: integration file is not exactly allowlisted" >&2; exit 2 ;;
esac

: "${RESOURCE_RUN_ID:?RESOURCE_RUN_ID is required}"
: "${POSTGRES_SENTINEL_PATH:?POSTGRES_SENTINEL_PATH is required}"
: "${POSTGRES_IMAGE_REFERENCE:?POSTGRES_IMAGE_REFERENCE is required}"
: "${POSTGRES_TEST_PASSWORD:?POSTGRES_TEST_PASSWORD is required in process memory}"
if [ "$NEED_REDIS" = true ]; then
    : "${REDIS_SENTINEL_PATH:?REDIS_SENTINEL_PATH is required}"
    : "${REDIS_IMAGE_REFERENCE:?REDIS_IMAGE_REFERENCE is required}"
fi

unset DATABASE_URL REDIS_URL
export ENVIRONMENT=test
export MARKETINGOS_TEST_MODE=integration
export MARKETINGOS_TEST_RESOURCE_SCOPE=disposable
export TEST_RUN_ID="$RESOURCE_RUN_ID"
export SECRET_KEY="test-only-synthetic-secret-at-least-32-bytes"
export OPENAI_API_KEY="test-only-not-a-live-key"
export OAUTH_TOKEN_ENCRYPTION_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
export API_DOCS_ENABLED=false
export REAL_PUBLISH_ENABLED=false
export META_PUBLISH_TRANSPORT_ENABLED=false
export META_PUBLISH_CANARY_MODE_ENABLED=true
export PYTHONPATH="${BACKEND_ROOT}:${BACKEND_ROOT}/tests"

cd "$BACKEND_ROOT"
exec python3 -m _integration_single_file_runner "../$1" "$NEED_REDIS"
