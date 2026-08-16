import asyncio
import logging
import re
import uuid
from types import SimpleNamespace

import httpx

import app.api.oauth_connections as oauth
import app.main as main


REQUEST_ID_RE = re.compile(
    r"^[0-9a-f]{32}$"
)


class FakeResult:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class FakeDB:
    def __init__(self, user):
        self._user = user

    async def execute(self, statement):
        return FakeResult(self._user)


async def request(
    path: str,
):
    transport = httpx.ASGITransport(
        app=main.app,
    )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.get(path)


def configure_log_capture(caplog):
    caplog.set_level(
        logging.WARNING,
    )

    caplog.set_level(
        logging.INFO,
        logger="app.core.request_context",
    )

    caplog.set_level(
        logging.WARNING,
        logger="app.api.oauth_connections",
    )


def assert_request_id_correlated(
    response,
    log_text,
):
    request_id = response.headers[
        "x-request-id"
    ]

    assert REQUEST_ID_RE.fullmatch(
        request_id
    )

    assert (
        f"request_id={request_id}"
        in log_text
    )

    return request_id


def test_health_exception_details_are_not_logged(
    monkeypatch,
    caplog,
):
    async def run():
        database_secret = (
            "DB_PASSWORD_SUPER_SECRET_123"
        )

        redis_secret = (
            "REDIS_URL_SUPER_SECRET_456"
        )

        async def broken_database():
            raise RuntimeError(
                database_secret
            )

        async def broken_redis():
            raise RuntimeError(
                redis_secret
            )

        monkeypatch.setattr(
            main,
            "check_database",
            broken_database,
        )

        monkeypatch.setattr(
            main,
            "check_redis",
            broken_redis,
        )

        configure_log_capture(caplog)
        caplog.clear()

        response = await request(
            "/api/health"
        )

        assert response.status_code == 503

        body = response.json()

        assert body["status"] == "degraded"
        assert (
            body["services"]["api"]
            is True
        )
        assert (
            body["services"]["database"]
            is False
        )
        assert (
            body["services"]["redis"]
            is False
        )

        text = caplog.text

        assert_request_id_correlated(
            response,
            text,
        )

        assert (
            text.count(
                "health_dependency_check_failed"
            )
            == 2
        )

        assert database_secret not in text
        assert redis_secret not in text
        assert "RuntimeError" not in text
        assert "Traceback" not in text

    asyncio.run(run())


def test_meta_exchange_exception_details_and_query_secrets_not_logged(
    monkeypatch,
    caplog,
):
    async def run():
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()

        state_secret = (
            "STATE_SUPER_SECRET_111"
        )

        code_secret = (
            "CODE_SUPER_SECRET_222"
        )

        provider_secret = (
            "PROVIDER_EXCEPTION_SECRET_333"
        )

        payload = SimpleNamespace(
            user_id=user_id,
            workspace_id=workspace_id,
        )

        user = SimpleNamespace(
            id=user_id,
            is_active=True,
        )

        db = FakeDB(user)

        async def fake_get_db():
            yield db

        async def fake_state(
            state_value,
            *,
            expected_provider,
        ):
            assert state_value == state_secret
            assert expected_provider == "meta"
            return payload

        async def fake_workspace_write(
            db_value,
            user_value,
            workspace_value,
        ):
            assert db_value is db
            assert user_value is user
            assert (
                workspace_value
                == workspace_id
            )

        async def fake_exchange(code):
            assert code == code_secret

            raise oauth.MetaOAuthExchangeError(
                provider_secret
            )

        monkeypatch.setattr(
            oauth,
            "consume_and_verify_oauth_state_v2",
            fake_state,
        )

        monkeypatch.setattr(
            oauth,
            "require_workspace_write",
            fake_workspace_write,
        )

        monkeypatch.setattr(
            oauth,
            "exchange_code_for_access_token",
            fake_exchange,
        )

        main.app.dependency_overrides[
            oauth.get_db
        ] = fake_get_db

        configure_log_capture(caplog)
        caplog.clear()

        try:
            response = await request(
                "/api/oauth/meta/callback"
                f"?state={state_secret}"
                f"&code={code_secret}"
            )
        finally:
            main.app.dependency_overrides.pop(
                oauth.get_db,
                None,
            )

        assert response.status_code == 400

        assert response.json() == {
            "detail": (
                "Meta OAuth token exchange failed"
            )
        }

        text = caplog.text

        assert_request_id_correlated(
            response,
            text,
        )

        assert (
            "meta_oauth_token_exchange_failed"
            in text
        )

        assert state_secret not in text
        assert code_secret not in text
        assert provider_secret not in text

        assert "Traceback" not in text

    asyncio.run(run())


def test_meta_page_discovery_exception_details_and_tokens_not_logged(
    monkeypatch,
    caplog,
):
    async def run():
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()

        state_secret = (
            "STATE_SUPER_SECRET_444"
        )

        code_secret = (
            "CODE_SUPER_SECRET_555"
        )

        access_token_secret = (
            "META_ACCESS_TOKEN_SECRET_666"
        )

        provider_secret = (
            "PAGE_DISCOVERY_SECRET_777"
        )

        payload = SimpleNamespace(
            user_id=user_id,
            workspace_id=workspace_id,
        )

        user = SimpleNamespace(
            id=user_id,
            is_active=True,
        )

        db = FakeDB(user)

        async def fake_get_db():
            yield db

        async def fake_state(
            state_value,
            *,
            expected_provider,
        ):
            assert state_value == state_secret
            assert expected_provider == "meta"
            return payload

        async def fake_workspace_write(
            db_value,
            user_value,
            workspace_value,
        ):
            assert db_value is db
            assert user_value is user
            assert (
                workspace_value
                == workspace_id
            )

        async def fake_exchange(code):
            assert code == code_secret

            return SimpleNamespace(
                access_token=access_token_secret
            )

        async def fake_identity(
            access_token,
        ):
            assert (
                access_token
                == access_token_secret
            )

            return SimpleNamespace(
                id="test-meta-user"
            )

        async def fake_pages(
            access_token,
        ):
            assert (
                access_token
                == access_token_secret
            )

            raise (
                oauth.MetaOAuthPageDiscoveryError(
                    provider_secret
                )
            )

        monkeypatch.setattr(
            oauth,
            "consume_and_verify_oauth_state_v2",
            fake_state,
        )

        monkeypatch.setattr(
            oauth,
            "require_workspace_write",
            fake_workspace_write,
        )

        monkeypatch.setattr(
            oauth,
            "exchange_code_for_access_token",
            fake_exchange,
        )

        monkeypatch.setattr(
            oauth,
            "get_meta_user_identity",
            fake_identity,
        )

        monkeypatch.setattr(
            oauth,
            "get_meta_managed_pages",
            fake_pages,
        )

        main.app.dependency_overrides[
            oauth.get_db
        ] = fake_get_db

        configure_log_capture(caplog)
        caplog.clear()

        try:
            response = await request(
                "/api/oauth/meta/callback"
                f"?state={state_secret}"
                f"&code={code_secret}"
            )
        finally:
            main.app.dependency_overrides.pop(
                oauth.get_db,
                None,
            )

        assert response.status_code == 502

        assert response.json() == {
            "detail": (
                "Meta OAuth Page discovery failed"
            )
        }

        text = caplog.text

        assert_request_id_correlated(
            response,
            text,
        )

        assert (
            "meta_oauth_page_discovery_failed"
            in text
        )

        assert state_secret not in text
        assert code_secret not in text
        assert access_token_secret not in text
        assert provider_secret not in text

        assert "Traceback" not in text

    asyncio.run(run())
