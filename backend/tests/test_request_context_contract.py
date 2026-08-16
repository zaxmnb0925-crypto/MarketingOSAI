import asyncio
import logging
import re

import httpx
from fastapi import FastAPI, HTTPException

from app.core.request_context import (
    RequestContextMiddleware,
    get_request_id,
)


REQUEST_ID_RE = re.compile(
    r"^[0-9a-f]{32}$"
)


def build_app() -> FastAPI:
    app = FastAPI()

    app.add_middleware(
        RequestContextMiddleware
    )

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    @app.get("/context")
    async def context():
        await asyncio.sleep(0.01)

        return {
            "request_id": get_request_id()
        }

    @app.get("/handled-error")
    async def handled_error():
        raise HTTPException(
            status_code=418,
            detail="expected",
        )

    return app


async def get(
    app: FastAPI,
    path: str,
    headers=None,
):
    transport = httpx.ASGITransport(
        app=app
    )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.get(
            path,
            headers=headers,
        )


def test_success_request_id():
    async def run():
        app = build_app()

        first = await get(app, "/ok")
        second = await get(app, "/ok")

        assert first.status_code == 200
        assert first.json() == {"ok": True}

        first_id = first.headers[
            "x-request-id"
        ]
        second_id = second.headers[
            "x-request-id"
        ]

        assert REQUEST_ID_RE.fullmatch(
            first_id
        )
        assert REQUEST_ID_RE.fullmatch(
            second_id
        )
        assert first_id != second_id

    asyncio.run(run())


def test_client_request_id_not_trusted():
    async def run():
        app = build_app()

        supplied = "client-controlled-id"

        response = await get(
            app,
            "/ok",
            headers={
                "X-Request-ID": supplied,
            },
        )

        actual = response.headers[
            "x-request-id"
        ]

        assert actual != supplied
        assert REQUEST_ID_RE.fullmatch(
            actual
        )

    asyncio.run(run())


def test_handled_error_request_id():
    async def run():
        app = build_app()

        response = await get(
            app,
            "/handled-error",
        )

        assert response.status_code == 418

        assert REQUEST_ID_RE.fullmatch(
            response.headers[
                "x-request-id"
            ]
        )

    asyncio.run(run())


def test_404_request_id():
    async def run():
        app = build_app()

        response = await get(
            app,
            "/missing",
        )

        assert response.status_code == 404

        assert REQUEST_ID_RE.fullmatch(
            response.headers[
                "x-request-id"
            ]
        )

    asyncio.run(run())


def test_concurrent_context_isolation():
    async def run():
        app = build_app()

        transport = httpx.ASGITransport(
            app=app
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            responses = await asyncio.gather(
                *[
                    client.get("/context")
                    for _ in range(20)
                ]
            )

        ids = []

        for response in responses:
            header_id = response.headers[
                "x-request-id"
            ]
            body_id = response.json()[
                "request_id"
            ]

            assert header_id == body_id
            assert REQUEST_ID_RE.fullmatch(
                header_id
            )

            ids.append(header_id)

        assert len(set(ids)) == 20

    asyncio.run(run())


def test_query_secrets_not_logged(
    caplog,
):
    async def run():
        app = build_app()

        caplog.set_level(
            logging.INFO,
            logger=(
                "app.core.request_context"
            ),
        )

        response = await get(
            app,
            (
                "/ok?"
                "access_token=SUPERSECRET"
                "&state=SECRETSTATE"
            ),
        )

        assert response.status_code == 200

        text = caplog.text

        assert "SUPERSECRET" not in text
        assert "SECRETSTATE" not in text
        assert "access_token" not in text
        assert "state=" not in text

        assert "path=/ok" in text
        assert "status=200" in text
        assert "duration_ms=" in text

    asyncio.run(run())


def test_production_app_wiring():
    from app.main import app

    middleware_classes = [
        item.cls
        for item in app.user_middleware
    ]

    assert (
        RequestContextMiddleware
        in middleware_classes
    )
