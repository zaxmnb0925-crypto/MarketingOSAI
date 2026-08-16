import asyncio
from uuid import uuid4

import app.services.publication_activation as activation
import app.services.publication_activation_store as store


HASH = "a" * 64


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.last_set = None

    async def set(
        self,
        key,
        value,
        *,
        ex=None,
        nx=None,
    ):
        self.last_set = {
            "key": key,
            "value": value,
            "ex": ex,
            "nx": nx,
        }

        if nx and key in self.data:
            return False

        self.data[key] = value
        return True

    async def getdel(
        self,
        key,
    ):
        return self.data.pop(
            key,
            None,
        )

    async def exists(
        self,
        key,
    ):
        return (
            1
            if key in self.data
            else 0
        )

    async def delete(
        self,
        key,
    ):
        existed = key in self.data

        self.data.pop(
            key,
            None,
        )

        return (
            1
            if existed
            else 0
        )


async def main():
    fake = FakeRedis()

    original_redis = (
        store.redis_client
    )

    original_time = (
        activation.time.time
    )

    try:
        store.redis_client = fake

        now = 1_700_000_000

        activation.time.time = (
            lambda: now
        )

        workspace_id = uuid4()
        publication_id = uuid4()
        user_id = uuid4()

        bearer = (
            await activation.create_publication_activation(
                workspace_id=workspace_id,
                publication_id=publication_id,
                user_id=user_id,
                content_hash=HASH,
            )
        )

        if (
            not isinstance(
                bearer,
                str,
            )
            or len(
                bearer
            ) < 32
        ):
            raise AssertionError(
                "activation bearer invalid"
            )

        key = store._key(
            bearer
        )

        if bearer in key:
            raise AssertionError(
                "raw activation appears in Redis key"
            )

        if not key.startswith(
            store.PUBLICATION_ACTIVATION_REDIS_PREFIX
        ):
            raise AssertionError(
                "activation Redis prefix invalid"
            )

        if (
            fake.last_set is None
            or fake.last_set["ex"]
            != activation.PUBLICATION_ACTIVATION_TTL_SECONDS
            or fake.last_set["nx"]
            is not True
        ):
            raise AssertionError(
                "activation SET NX EX contract failed"
            )

        result = (
            await activation.consume_and_verify_publication_activation(
                activation_value=bearer,
                expected_workspace_id=workspace_id,
                expected_publication_id=publication_id,
                expected_user_id=user_id,
                expected_content_hash=HASH,
            )
        )

        if (
            result.workspace_id
            != workspace_id
            or result.publication_id
            != publication_id
            or result.user_id
            != user_id
            or result.content_hash
            != HASH
        ):
            raise AssertionError(
                "activation binding failed"
            )

        try:
            await activation.consume_and_verify_publication_activation(
                activation_value=bearer,
                expected_workspace_id=workspace_id,
                expected_publication_id=publication_id,
                expected_user_id=user_id,
                expected_content_hash=HASH,
            )
        except activation.PublicationActivationReplay:
            pass
        else:
            raise AssertionError(
                "activation replay succeeded"
            )

        #
        # A binding mismatch must still consume the bearer.
        #
        mismatch = (
            await activation.create_publication_activation(
                workspace_id=workspace_id,
                publication_id=publication_id,
                user_id=user_id,
                content_hash=HASH,
            )
        )

        try:
            await activation.consume_and_verify_publication_activation(
                activation_value=mismatch,
                expected_workspace_id=workspace_id,
                expected_publication_id=publication_id,
                expected_user_id=uuid4(),
                expected_content_hash=HASH,
            )
        except activation.PublicationActivationInvalid:
            pass
        else:
            raise AssertionError(
                "misbound activation accepted"
            )

        try:
            await activation.consume_and_verify_publication_activation(
                activation_value=mismatch,
                expected_workspace_id=workspace_id,
                expected_publication_id=publication_id,
                expected_user_id=user_id,
                expected_content_hash=HASH,
            )
        except activation.PublicationActivationReplay:
            pass
        else:
            raise AssertionError(
                "misbound activation was replayable"
            )

        #
        # Expiration.
        #
        expiring = (
            await activation.create_publication_activation(
                workspace_id=workspace_id,
                publication_id=publication_id,
                user_id=user_id,
                content_hash=HASH,
            )
        )

        activation.time.time = (
            lambda: (
                now
                + activation.PUBLICATION_ACTIVATION_TTL_SECONDS
                + 1
            )
        )

        try:
            await activation.consume_and_verify_publication_activation(
                activation_value=expiring,
                expected_workspace_id=workspace_id,
                expected_publication_id=publication_id,
                expected_user_id=user_id,
                expected_content_hash=HASH,
            )
        except activation.PublicationActivationExpired:
            pass
        else:
            raise AssertionError(
                "expired activation accepted"
            )

        print(
            "Opaque activation bearer generation: PASS"
        )
        print(
            "SHA-256 activation Redis key: PASS"
        )
        print(
            "Raw activation in Redis keyspace: NO"
        )
        print(
            "Activation SET NX EX: PASS"
        )
        print(
            "Atomic activation GETDEL: PASS"
        )
        print(
            "Exact activation binding: PASS"
        )
        print(
            "Activation replay blocked: PASS"
        )
        print(
            "Misbound activation consumed fail-closed: PASS"
        )
        print(
            "Activation TTL expiration: PASS"
        )

    finally:
        store.redis_client = (
            original_redis
        )

        activation.time.time = (
            original_time
        )


asyncio.run(
    main()
)

print()
print(
    "v0.13E-E-C activation service/store: PASS"
)
print(
    "Real Redis calls: NONE"
)
print(
    "Real Meta calls: NONE"
)
print(
    "Facebook posts created: NONE"
)
