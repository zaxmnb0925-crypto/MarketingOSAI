from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not any(
    handler.get_name()
    == "marketingos_request_context"
    for handler in logger.handlers
):
    request_log_handler = logging.StreamHandler()
    request_log_handler.set_name(
        "marketingos_request_context"
    )
    request_log_handler.setLevel(logging.INFO)
    request_log_handler.setFormatter(
        logging.Formatter("%(message)s")
    )
    logger.addHandler(request_log_handler)

_request_id: ContextVar[str | None] = ContextVar(
    "marketingos_request_id",
    default=None,
)

_REQUEST_ID_HEADER = b"x-request-id"


def get_request_id() -> str | None:
    return _request_id.get()


class RequestContextMiddleware:
    def __init__(
        self,
        app: ASGIApp,
    ) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(
                scope,
                receive,
                send,
            )
            return

        request_id = uuid.uuid4().hex
        context_token = _request_id.set(
            request_id
        )

        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(
            message: Message,
        ) -> None:
            nonlocal status_code

            if (
                message["type"]
                == "http.response.start"
            ):
                status_code = int(
                    message["status"]
                )

                headers = [
                    (key, value)
                    for key, value
                    in message.get(
                        "headers",
                        [],
                    )
                    if (
                        key.lower()
                        != _REQUEST_ID_HEADER
                    )
                ]

                headers.append(
                    (
                        _REQUEST_ID_HEADER,
                        request_id.encode(
                            "ascii"
                        ),
                    )
                )

                message = {
                    **message,
                    "headers": headers,
                }

            await send(message)

        try:
            await self.app(
                scope,
                receive,
                send_with_request_id,
            )

        except Exception:
            duration_ms = (
                time.perf_counter()
                - started
            ) * 1000

            logger.error(
                (
                    "request_failed "
                    "request_id=%s "
                    "method=%s "
                    "path=%s "
                    "status=500 "
                    "duration_ms=%.3f"
                ),
                request_id,
                scope.get(
                    "method",
                    "UNKNOWN",
                ),
                scope.get(
                    "path",
                    "",
                ),
                duration_ms,
            )

            raise

        else:
            duration_ms = (
                time.perf_counter()
                - started
            ) * 1000

            logger.info(
                (
                    "request_completed "
                    "request_id=%s "
                    "method=%s "
                    "path=%s "
                    "status=%s "
                    "duration_ms=%.3f"
                ),
                request_id,
                scope.get(
                    "method",
                    "UNKNOWN",
                ),
                scope.get(
                    "path",
                    "",
                ),
                status_code,
                duration_ms,
            )

        finally:
            _request_id.reset(
                context_token
            )
