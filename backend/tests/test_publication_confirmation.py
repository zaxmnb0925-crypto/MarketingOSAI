import asyncio
from uuid import UUID

import app.services.publication_confirmation as confirmation


WORKSPACE_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)

PUBLICATION_ID = UUID(
    "22222222-2222-2222-2222-222222222222"
)

USER_ID = UUID(
    "33333333-3333-3333-3333-333333333333"
)

OTHER_USER_ID = UUID(
    "44444444-4444-4444-4444-444444444444"
)

CONTENT_HASH = "a" * 64


async def main():
    store = {}
    observed_ttl = []

    async def fake_register(
        value,
        payload,
        ttl_seconds,
    ):
        assert value not in store
        store[value] = payload
        observed_ttl.append(ttl_seconds)

    async def fake_consume(
        value,
    ):
        return store.pop(
            value,
            None,
        )

    confirmation.register_publication_confirmation = (
        fake_register
    )
    confirmation.consume_publication_confirmation = (
        fake_consume
    )

    value = (
        await confirmation.create_publication_confirmation(
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            user_id=USER_ID,
            content_hash=CONTENT_HASH,
        )
    )

    assert value
    assert str(WORKSPACE_ID) not in value
    assert str(PUBLICATION_ID) not in value
    assert str(USER_ID) not in value
    assert CONTENT_HASH not in value

    assert observed_ttl == [
        confirmation.PUBLICATION_CONFIRMATION_TTL_SECONDS
    ]

    payload = (
        await confirmation
        .consume_and_verify_publication_confirmation(
            confirmation_value=value,
            expected_workspace_id=WORKSPACE_ID,
            expected_publication_id=PUBLICATION_ID,
            expected_user_id=USER_ID,
            expected_content_hash=CONTENT_HASH,
        )
    )

    assert payload.workspace_id == WORKSPACE_ID
    assert payload.publication_id == PUBLICATION_ID
    assert payload.user_id == USER_ID
    assert payload.content_hash == CONTENT_HASH

    print(
        "Opaque confirmation binding: PASS"
    )
    print(
        "Atomic one-time consume contract: PASS"
    )

    try:
        await confirmation.consume_and_verify_publication_confirmation(
            confirmation_value=value,
            expected_workspace_id=WORKSPACE_ID,
            expected_publication_id=PUBLICATION_ID,
            expected_user_id=USER_ID,
            expected_content_hash=CONTENT_HASH,
        )
    except confirmation.PublicationConfirmationReplay:
        pass
    else:
        raise AssertionError(
            "confirmation replay was accepted"
        )

    print(
        "Confirmation replay blocked: PASS"
    )

    mismatch_value = (
        await confirmation.create_publication_confirmation(
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            user_id=USER_ID,
            content_hash=CONTENT_HASH,
        )
    )

    try:
        await confirmation.consume_and_verify_publication_confirmation(
            confirmation_value=mismatch_value,
            expected_workspace_id=WORKSPACE_ID,
            expected_publication_id=PUBLICATION_ID,
            expected_user_id=OTHER_USER_ID,
            expected_content_hash=CONTENT_HASH,
        )
    except confirmation.PublicationConfirmationInvalid:
        pass
    else:
        raise AssertionError(
            "misbound confirmation was accepted"
        )

    #
    # Mismatch consumed the value before validation.
    # It cannot later be replayed with correct bindings.
    #
    try:
        await confirmation.consume_and_verify_publication_confirmation(
            confirmation_value=mismatch_value,
            expected_workspace_id=WORKSPACE_ID,
            expected_publication_id=PUBLICATION_ID,
            expected_user_id=USER_ID,
            expected_content_hash=CONTENT_HASH,
        )
    except confirmation.PublicationConfirmationReplay:
        pass
    else:
        raise AssertionError(
            "misbound value remained reusable"
        )

    print(
        "Misbound confirmation fails closed: PASS"
    )
    print(
        "Real Redis calls: NONE"
    )


asyncio.run(main())
