FROM docker.io/library/postgres@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685

USER root

RUN set -eux; \
    apk upgrade --no-cache; \
    apk add --no-cache su-exec; \
    entrypoint="/usr/local/bin/docker-entrypoint.sh"; \
    test -f "$entrypoint"; \
    test "$(grep -Fc 'exec gosu postgres "$BASH_SOURCE" "$@"' "$entrypoint")" -eq 1; \
    sed -i 's/exec gosu postgres "$BASH_SOURCE" "$@"/exec su-exec postgres "$BASH_SOURCE" "$@"/' "$entrypoint"; \
    test "$(grep -Fc 'exec su-exec postgres "$BASH_SOURCE" "$@"' "$entrypoint")" -eq 1; \
    if grep -Eq '(^|[^[:alnum:]_])gosu([^[:alnum:]_]|$)' "$entrypoint"; then exit 1; fi; \
    test -x "$(command -v su-exec)"; \
    rm -f /usr/local/bin/gosu; \
    if command -v gosu >/dev/null 2>&1; then exit 1; fi; \
    test ! -e /usr/local/bin/gosu

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
