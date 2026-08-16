import asyncio
import io
import logging
import re
import subprocess
import sys

import httpx

import app.core.request_context as request_context
import app.main as main


REQUEST_ID_RE = re.compile(
    r"^[0-9a-f]{32}$"
)

HANDLER_NAME = (
    "marketingos_request_context"
)


def dedicated_handlers():
    return [
        handler
        for handler
        in request_context.logger.handlers
        if handler.get_name() == HANDLER_NAME
    ]


async def request(path: str):
    transport = httpx.ASGITransport(
        app=main.app,
    )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.get(path)


def test_request_logger_configuration_contract():
    handlers = dedicated_handlers()

    assert len(handlers) == 1

    handler = handlers[0]

    assert (
        request_context.logger.level
        == logging.INFO
    )

    assert isinstance(
        handler,
        logging.StreamHandler,
    )

    assert handler.level == logging.INFO

    assert handler.formatter is not None

    assert (
        handler.formatter._fmt
        == "%(message)s"
    )


def test_request_completion_is_stream_visible_and_secret_safe():
    async def run():
        handlers = dedicated_handlers()

        assert len(handlers) == 1

        handler = handlers[0]

        capture = io.StringIO()

        original_stream = handler.stream

        secret = (
            "QUERY_SECRET_"
            "DO_NOT_LOG_123456789"
        )

        try:
            handler.setStream(capture)

            response = await request(
                "/__request_logger_contract"
                f"?probe={secret}"
            )
        finally:
            handler.setStream(
                original_stream
            )

        assert response.status_code == 404

        request_id = response.headers[
            "x-request-id"
        ]

        assert REQUEST_ID_RE.fullmatch(
            request_id
        )

        text = capture.getvalue()

        assert "request_completed" in text

        assert (
            f"request_id={request_id}"
            in text
        )

        assert "method=GET" in text

        assert (
            "path=/__request_logger_contract"
            in text
        )

        assert "status=404" in text

        assert secret not in text

        assert "?probe=" not in text

        matching = [
            line
            for line in text.splitlines()
            if request_id in line
        ]

        assert len(matching) == 1

    asyncio.run(run())


def test_request_logger_configuration_is_reload_idempotent():
    code = r'''
import importlib

import app.core.request_context as rc

name = "marketingos_request_context"

def count():
    return sum(
        handler.get_name() == name
        for handler in rc.logger.handlers
    )

assert count() == 1

importlib.reload(rc)

assert count() == 1

importlib.reload(rc)

assert count() == 1

print("reload_idempotent=PASS")
'''

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        result.stdout
        + result.stderr
    )

    assert (
        "reload_idempotent=PASS"
        in result.stdout
    )
