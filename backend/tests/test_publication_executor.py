import asyncio
from dataclasses import dataclass
from uuid import UUID

import httpx

import app.services.publication_executor as executor
from app.services.meta_publishing import (
    MetaGraphHTTPTransport,
)
from app.services.publication_workflow import (
    PublicationValidationError,
)


WORKSPACE_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)

PUBLICATION_ID = UUID(
    "22222222-2222-2222-2222-222222222222"
)

TRIGGER_USER_ID = UUID(
    "33333333-3333-3333-3333-333333333333"
)

PAGE_ID = "1234567890"

FAKE_CIPHERTEXT = (
    "FAKE_CIPHERTEXT_NOT_REAL"
)

FAKE_TOKEN = (
    "FAKE_PAGE_TOKEN_NOT_REAL"
)

MESSAGE = (
    "v0.13D executor mock-only content"
)


@dataclass
class State:
    status: str = "approved"
    attempts: int = 0
    provider_post_id: str | None = None
    last_error: str | None = None
    network_calls: int = 0
    decrypt_calls: int = 0


class FakeDB:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeCipher:
    def __init__(
        self,
        state: State,
        *,
        fail: bool = False,
    ):
        self.state = state
        self.fail = fail

    def decrypt(self, ciphertext: str) -> str:
        self.state.decrypt_calls += 1

        assert (
            ciphertext == FAKE_CIPHERTEXT
        )

        if self.fail:
            raise RuntimeError(
                "SECRET_DECRYPT_EXCEPTION"
            )

        return FAKE_TOKEN


def install_fakes(
    state: State,
    *,
    loader_error: Exception | None = None,
    decrypt_fail: bool = False,
):
    async def begin(
        db,
        workspace_id,
        publication_id,
        triggered_by_user_id,
    ):
        assert state.status == "approved"
        assert (
            triggered_by_user_id
            == TRIGGER_USER_ID
        )
        state.status = "publishing"
        state.attempts += 1

    async def load(
        db,
        workspace_id,
        publication_id,
    ):
        if loader_error is not None:
            raise loader_error

        assert state.status == "publishing"

        return executor.PublicationExecutionContext(
            page_id=PAGE_ID,
            message=MESSAGE,
            content_hash="mock-hash",
            access_token_ciphertext=(
                FAKE_CIPHERTEXT
            ),
        )

    async def published(
        db,
        workspace_id,
        publication_id,
        provider_post_id,
        provider_permalink=None,
    ):
        assert state.status == "publishing"
        state.status = "published"
        state.provider_post_id = (
            provider_post_id
        )
        state.last_error = None

    async def failed(
        db,
        workspace_id,
        publication_id,
        safe_error,
    ):
        assert state.status == "publishing"
        state.status = "failed"
        state.last_error = safe_error

    async def unknown(
        db,
        workspace_id,
        publication_id,
        safe_error=(
            "Publishing outcome is unknown; "
            "manual reconciliation required"
        ),
    ):
        assert state.status == "publishing"

        # Intentionally remain publishing.
        state.last_error = safe_error

    executor.begin_publication_attempt = begin
    executor._load_execution_context = load
    executor.mark_publication_published = (
        published
    )
    executor.mark_publication_failed = failed
    executor.mark_publication_execution_unknown = (
        unknown
    )
    executor.oauth_token_cipher = FakeCipher(
        state,
        fail=decrypt_fail,
    )


async def success_case():
    state = State()
    db = FakeDB()

    install_fakes(state)

    async def handler(
        request: httpx.Request,
    ):
        #
        # The durable publishing claim MUST already
        # be committed before provider execution.
        #
        assert db.commits == 1
        assert state.status == "publishing"
        assert state.attempts == 1

        state.network_calls += 1

        assert (
            "access_token"
            not in request.url.params
        )

        assert (
            request.headers.get(
                "Authorization"
            )
            == f"Bearer {FAKE_TOKEN}"
        )

        return httpx.Response(
            200,
            json={
                "id": "1234567890_987654321",
            },
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    result = (
        await executor.execute_meta_publication_with_transport(
            db=db,
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            triggered_by_user_id=TRIGGER_USER_ID,
            transport=transport,
        )
    )

    assert result.provider_post_id == (
        "1234567890_987654321"
    )

    assert state.status == "published"
    assert state.attempts == 1
    assert state.network_calls == 1
    assert state.decrypt_calls == 1
    assert db.commits == 2

    print(
        "durable claim before provider call: PASS"
    )
    print(
        "confirmed success -> published: PASS"
    )


async def definite_rejection_case():
    state = State()
    db = FakeDB()

    install_fakes(state)

    async def handler(
        request: httpx.Request,
    ):
        assert db.commits == 1
        assert state.status == "publishing"

        state.network_calls += 1

        return httpx.Response(
            400,
            json={
                "error": {
                    "message":
                        "SECRET_PROVIDER_MESSAGE",
                    "type":
                        "OAuthException",
                    "code":
                        200,
                }
            },
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    try:
        await executor.execute_meta_publication_with_transport(
            db=db,
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            triggered_by_user_id=TRIGGER_USER_ID,
            transport=transport,
        )
    except executor.PublicationExecutionProviderRejected as exc:
        safe = str(exc)

        assert "SECRET_PROVIDER_MESSAGE" not in safe
        assert FAKE_TOKEN not in safe
    else:
        raise AssertionError(
            "provider rejection did not fail"
        )

    assert state.status == "failed"
    assert state.network_calls == 1
    assert state.attempts == 1
    assert db.commits == 2

    print(
        "definite rejection -> failed: PASS"
    )
    print(
        "provider error secret isolation: PASS"
    )


async def unknown_timeout_case():
    state = State()
    db = FakeDB()

    install_fakes(state)

    async def handler(
        request: httpx.Request,
    ):
        assert db.commits == 1
        assert state.status == "publishing"

        state.network_calls += 1

        raise httpx.ReadTimeout(
            "SECRET_TIMEOUT_DETAIL",
            request=request,
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    try:
        await executor.execute_meta_publication_with_transport(
            db=db,
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            triggered_by_user_id=TRIGGER_USER_ID,
            transport=transport,
        )
    except executor.PublicationExecutionOutcomeUnknown as exc:
        safe = str(exc)

        assert "SECRET_TIMEOUT_DETAIL" not in safe
        assert FAKE_TOKEN not in safe
    else:
        raise AssertionError(
            "timeout was not outcome-unknown"
        )

    #
    # Critical:
    # ambiguous outcome stays publishing.
    # It does NOT become approved or ordinary failed.
    #
    assert state.status == "publishing"
    assert state.network_calls == 1
    assert state.attempts == 1
    assert db.commits == 2
    assert (
        "manual reconciliation"
        in state.last_error
    )

    print(
        "timeout -> reconciliation state: PASS"
    )
    print(
        "ambiguous outcome remains non-retryable: PASS"
    )


async def preflight_failure_case():
    state = State()
    db = FakeDB()

    install_fakes(
        state,
        loader_error=PublicationValidationError(
            "SECRET_INTERNAL_VALIDATION"
        ),
    )

    called = False

    async def handler(
        request: httpx.Request,
    ):
        nonlocal called
        called = True

        raise AssertionError(
            "network must not run"
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    try:
        await executor.execute_meta_publication_with_transport(
            db=db,
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            triggered_by_user_id=TRIGGER_USER_ID,
            transport=transport,
        )
    except executor.PublicationExecutionError as exc:
        assert (
            str(exc)
            == "Publication execution validation failed"
        )
    else:
        raise AssertionError(
            "preflight failure accepted"
        )

    assert called is False
    assert state.network_calls == 0
    assert state.decrypt_calls == 0
    assert state.status == "failed"
    assert db.commits == 2

    print(
        "post-claim preflight failure blocks network: PASS"
    )


async def decrypt_failure_case():
    state = State()
    db = FakeDB()

    install_fakes(
        state,
        decrypt_fail=True,
    )

    called = False

    async def handler(
        request: httpx.Request,
    ):
        nonlocal called
        called = True

        raise AssertionError(
            "network must not run"
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    try:
        await executor.execute_meta_publication_with_transport(
            db=db,
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            triggered_by_user_id=TRIGGER_USER_ID,
            transport=transport,
        )
    except executor.PublicationExecutionError as exc:
        safe = str(exc)

        assert (
            safe
            == (
                "Social account credential "
                "could not be decrypted"
            )
        )

        assert (
            "SECRET_DECRYPT_EXCEPTION"
            not in safe
        )
    else:
        raise AssertionError(
            "decrypt failure accepted"
        )

    assert called is False
    assert state.network_calls == 0
    assert state.decrypt_calls == 1
    assert state.status == "failed"
    assert db.commits == 2

    print(
        "decrypt failure blocks network: PASS"
    )
    print(
        "decrypt exception isolation: PASS"
    )


async def main():
    await success_case()
    await definite_rejection_case()
    await unknown_timeout_case()
    await preflight_failure_case()
    await decrypt_failure_case()

    print()
    print(
        "Publication executor mock safety tests: PASS"
    )
    print(
        "Real Meta network calls: NONE"
    )
    print(
        "Real Facebook posts created: NONE"
    )


asyncio.run(main())
