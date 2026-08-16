#!/usr/bin/env bash
set -u

PROJECT_ROOT="/opt/MarketingOSAI"

cd "$PROJECT_ROOT" || exit 1

if [ "$(id -u)" != "0" ]; then
    echo "STOP: regression runner must run as root"
    exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"

NET="marketingos-regression-${STAMP}"
DB="marketingos-regression-db-${STAMP}"
REDIS="marketingos-regression-redis-${STAMP}"
RUNNER="marketingos-regression-runner-${STAMP}"

BASE_TAG="marketingos-backend:v013h-regression-base-${STAMP}"
TEST_IMAGE="marketingos-backend:v013h-regression-${STAMP}"

PASS_COUNT=0
FAIL_COUNT=0

FAIL_LIST="/tmp/marketingos_regression_failures_${STAMP}.txt"
: > "$FAIL_LIST"


cleanup() {
    docker rm -f \
        "$RUNNER" \
        "$DB" \
        "$REDIS" \
        >/dev/null 2>&1 || true

    docker network rm \
        "$NET" \
        >/dev/null 2>&1 || true

    docker image rm \
        "$TEST_IMAGE" \
        >/dev/null 2>&1 || true

    docker image rm \
        "$BASE_TAG" \
        >/dev/null 2>&1 || true
}

trap cleanup EXIT


is_success() {
    RC="$1"
    LOG="$2"

    if [ "$RC" = "0" ]; then
        return 0
    fi

    #
    # Several legacy files execute their assertions during module
    # import. Successful execution may therefore leave pytest with
    # zero collected test functions and exit status 5.
    #
    if [ "$RC" = "5" ]; then
        if ! grep -Eq \
            '(^|[[:space:]])ERROR([[:space:]]|$)|(^|[[:space:]])FAILED([[:space:]]|$)|Traceback|AssertionError|E[[:space:]]+[A-Za-z_][A-Za-z0-9_.]*Error:' \
            "$LOG"
        then
            return 0
        fi
    fi

    return 1
}


reset_state() {
    docker exec "$DB" \
        psql \
        -U marketingos_test \
        -d marketingos_test \
        -v ON_ERROR_STOP=1 \
        -c '
            DROP SCHEMA public CASCADE;
            CREATE SCHEMA public;
        ' \
        >/dev/null

    docker exec "$RUNNER" \
        alembic upgrade head \
        >/dev/null

    docker exec "$REDIS" \
        redis-cli FLUSHALL \
        >/dev/null
}


echo "======================================================"
echo " MarketingOS CANONICAL BACKEND REGRESSION"
echo " PROCESS-ISOLATED / POSTGRES / REDIS"
echo "======================================================"


echo
echo "===== PRODUCTION SAFETY PREFLIGHT ====="

BACKEND_CID_BEFORE="$(docker compose ps -q backend)"
FRONTEND_CID_BEFORE="$(docker compose ps -q frontend)"
DB_CID_BEFORE="$(docker compose ps -q db)"
REDIS_CID_BEFORE="$(docker compose ps -q redis)"

BACKEND_IMAGE="$(
    docker inspect "$BACKEND_CID_BEFORE" \
        --format '{{.Image}}'
)"

FRONTEND_IMAGE="$(
    docker inspect "$FRONTEND_CID_BEFORE" \
        --format '{{.Image}}'
)"

HEALTH="$(
    curl -sS \
        -o /dev/null \
        -w '%{http_code}' \
        http://127.0.0.1:8100/api/health
)"

FLAGS_BEFORE="$(
docker compose exec -T backend python -c '
from app.core.config import settings

print("api_docs_enabled=" + str(settings.api_docs_enabled).lower())
print("real_publish_enabled=" + str(settings.real_publish_enabled).lower())
print("meta_publish_transport_enabled=" + str(settings.meta_publish_transport_enabled).lower())
print("meta_publish_canary_mode_enabled=" + str(settings.meta_publish_canary_mode_enabled).lower())
'
)"

EXPECTED_FLAGS='api_docs_enabled=false
real_publish_enabled=false
meta_publish_transport_enabled=false
meta_publish_canary_mode_enabled=true'

if \
    [ "$HEALTH" != "200" ] || \
    [ "$FLAGS_BEFORE" != "$EXPECTED_FLAGS" ]
then
    echo "OVERALL=STOP_AND_REVIEW"
    echo "REASON=PRODUCTION_PREFLIGHT"
    exit 1
fi

echo "production_preflight=PASS"


echo
echo "===== BUILD DISPOSABLE TEST IMAGE ====="

docker tag \
    "$BACKEND_IMAGE" \
    "$BASE_TAG"

docker build \
    --build-arg "BASE_IMAGE=$BASE_TAG" \
    -f backend/Dockerfile.test \
    -t "$TEST_IMAGE" \
    backend

if [ "$?" != "0" ]; then
    echo "OVERALL=STOP_AND_REVIEW"
    echo "REASON=TEST_IMAGE_BUILD"
    exit 1
fi

echo "test_image=PASS"


echo
echo "===== CREATE ISOLATED INFRA ====="

docker network create "$NET" \
    >/dev/null

DB_PASSWORD="$(
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"

docker run -d \
    --name "$DB" \
    --network "$NET" \
    -e POSTGRES_DB=marketingos_test \
    -e POSTGRES_USER=marketingos_test \
    -e "POSTGRES_PASSWORD=$DB_PASSWORD" \
    postgres:16-alpine \
    >/dev/null

docker run -d \
    --name "$REDIS" \
    --network "$NET" \
    redis:7-alpine \
    >/dev/null

DB_READY="NO"
REDIS_READY="NO"

for attempt in $(seq 1 30); do

    if docker exec "$DB" \
        pg_isready \
        -U marketingos_test \
        -d marketingos_test \
        >/dev/null 2>&1
    then
        DB_READY="YES"
    fi

    if docker exec "$REDIS" \
        redis-cli ping \
        2>/dev/null \
        | grep -q '^PONG$'
    then
        REDIS_READY="YES"
    fi

    if \
        [ "$DB_READY" = "YES" ] && \
        [ "$REDIS_READY" = "YES" ]
    then
        break
    fi

    sleep 1
done

if \
    [ "$DB_READY" != "YES" ] || \
    [ "$REDIS_READY" != "YES" ]
then
    echo "OVERALL=STOP_AND_REVIEW"
    echo "REASON=ISOLATED_INFRA"
    exit 1
fi

echo "postgres=PASS"
echo "redis=PASS"


echo
echo "===== CREATE TEST RUNNER ====="

TEST_SECRET="$(
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

TEST_FERNET="$(
docker run --rm \
    "$TEST_IMAGE" \
    python -c '
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
'
)"

DATABASE_URL="postgresql+asyncpg://marketingos_test:${DB_PASSWORD}@${DB}:5432/marketingos_test"
REDIS_URL="redis://${REDIS}:6379/0"

docker create \
    --name "$RUNNER" \
    --network "$NET" \
    -e ENVIRONMENT=test \
    -e "DATABASE_URL=$DATABASE_URL" \
    -e "TEST_DATABASE_URL=$DATABASE_URL" \
    -e "REDIS_URL=$REDIS_URL" \
    -e "TEST_REDIS_URL=$REDIS_URL" \
    -e "SECRET_KEY=$TEST_SECRET" \
    -e OPENAI_API_KEY=test-only-not-real \
    -e "OAUTH_TOKEN_ENCRYPTION_KEY=$TEST_FERNET" \
    -e API_DOCS_ENABLED=false \
    -e REAL_PUBLISH_ENABLED=false \
    -e META_PUBLISH_TRANSPORT_ENABLED=false \
    -e META_PUBLISH_CANARY_MODE_ENABLED=true \
    "$TEST_IMAGE" \
    sleep infinity \
    >/dev/null

docker start "$RUNNER" >/dev/null


echo
echo "===== PROCESS-ISOLATED TEST FILES ====="

mapfile -t TEST_FILES < <(
    find backend/tests \
        -maxdepth 1 \
        -type f \
        -name 'test_*.py' \
        -printf '%f\n' \
    | sort
)

TOTAL_COUNT="${#TEST_FILES[@]}"

for TEST_FILE in "${TEST_FILES[@]}"; do

    echo
    echo "TEST_FILE=$TEST_FILE"

    reset_state

    LOG="/tmp/marketingos_regression_${STAMP}_${TEST_FILE}.log"

    set +e

    docker exec "$RUNNER" \
        python -m pytest \
        -q \
        --disable-warnings \
        -p _v013h_legacy_target_compat \
        "/app/tests/${TEST_FILE}" \
        > "$LOG" \
        2>&1

    RC="$?"

    set -e

    cat "$LOG"

    if is_success "$RC" "$LOG"; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "FILE_RESULT=PASS"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "$TEST_FILE" >> "$FAIL_LIST"
        echo "FILE_RESULT=FAIL"
        tail -n 180 "$LOG"
    fi
done


echo
echo "===== PRODUCTION UNTOUCHED GATE ====="

BACKEND_CID_AFTER="$(docker compose ps -q backend)"
FRONTEND_CID_AFTER="$(docker compose ps -q frontend)"
DB_CID_AFTER="$(docker compose ps -q db)"
REDIS_CID_AFTER="$(docker compose ps -q redis)"

BACKEND_IMAGE_AFTER="$(
    docker inspect "$BACKEND_CID_AFTER" \
        --format '{{.Image}}'
)"

FRONTEND_IMAGE_AFTER="$(
    docker inspect "$FRONTEND_CID_AFTER" \
        --format '{{.Image}}'
)"

HEALTH_AFTER="$(
    curl -sS \
        -o /dev/null \
        -w '%{http_code}' \
        http://127.0.0.1:8100/api/health
)"

FLAGS_AFTER="$(
docker compose exec -T backend python -c '
from app.core.config import settings

print("api_docs_enabled=" + str(settings.api_docs_enabled).lower())
print("real_publish_enabled=" + str(settings.real_publish_enabled).lower())
print("meta_publish_transport_enabled=" + str(settings.meta_publish_transport_enabled).lower())
print("meta_publish_canary_mode_enabled=" + str(settings.meta_publish_canary_mode_enabled).lower())
'
)"

PROD_PASS="NO"

if \
    [ "$BACKEND_CID_AFTER" = "$BACKEND_CID_BEFORE" ] && \
    [ "$FRONTEND_CID_AFTER" = "$FRONTEND_CID_BEFORE" ] && \
    [ "$DB_CID_AFTER" = "$DB_CID_BEFORE" ] && \
    [ "$REDIS_CID_AFTER" = "$REDIS_CID_BEFORE" ] && \
    [ "$BACKEND_IMAGE_AFTER" = "$BACKEND_IMAGE" ] && \
    [ "$FRONTEND_IMAGE_AFTER" = "$FRONTEND_IMAGE" ] && \
    [ "$HEALTH_AFTER" = "200" ] && \
    [ "$FLAGS_AFTER" = "$EXPECTED_FLAGS" ]
then
    PROD_PASS="YES"
fi


echo
echo "======================================================"
echo " REGRESSION RESULT"
echo "======================================================"

echo "TEST_FILES=$TOTAL_COUNT"
echo "PASS_FILES=$PASS_COUNT"
echo "FAIL_FILES=$FAIL_COUNT"
echo "PRODUCTION_UNTOUCHED=$PROD_PASS"

if [ "$FAIL_COUNT" != "0" ]; then
    echo
    echo "FAILED_FILES:"
    cat "$FAIL_LIST"
fi

if \
    [ "$FAIL_COUNT" = "0" ] && \
    [ "$PASS_COUNT" = "$TOTAL_COUNT" ] && \
    [ "$PROD_PASS" = "YES" ]
then
    echo
    echo "OVERALL=PROCESS_ISOLATED_REGRESSION_FULL_PASS"
    exit 0
fi

echo
echo "OVERALL=STOP_AND_REVIEW"
exit 1
