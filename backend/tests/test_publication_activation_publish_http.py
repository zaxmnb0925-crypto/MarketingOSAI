import asyncio
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import Response

from app.core.rate_limit import (
    enforce_rate_limit as application_enforce_rate_limit,
)

import sys as _publication_compat_sys
from pathlib import Path as _publication_compat_Path

_publication_compat_dir = str(
    _publication_compat_Path(
        __file__
    ).resolve().parent
)

if (
    _publication_compat_dir
    not in _publication_compat_sys.path
):
    _publication_compat_sys.path.insert(
        0,
        _publication_compat_dir,
    )

from _publication_test_compat import (
    publication_publishing_source_path,
    publication_source_paths,
    publication_source_text,
    publications,
)

from app.models.publication import (
    PublicationStatus,
)
from app.schemas.publication import (
    PublicationPublishRequest,
)


WORKSPACE_ID = uuid4()
PUBLICATION_ID = uuid4()
USER_ID = uuid4()

ACTIVATION = (
    "activation-http-test-"
    + ("y" * 32)
)

CONFIRMATION = (
    "confirmation-http-test-"
    + ("z" * 32)
)

CONTENT_HASH = (
    "c" * 64
)

#
# v0.13G legacy activation HTTP fixture:
# this isolated regression suite exercises gates after
# exact canary target-policy validation.
#
publications.settings.meta_publish_canary_mode_enabled = True
publications.settings.meta_publish_canary_workspace_id = WORKSPACE_ID
publications.settings.meta_publish_canary_publication_id = PUBLICATION_ID


class FakeDB:
    pass


class FakeTransport:
    pass


def payload():
    return PublicationPublishRequest(
        activation=ACTIVATION,
        confirmation=CONFIRMATION,
        content_hash=CONTENT_HASH,
    )


async def main():
    originals = (
        application_enforce_rate_limit,
        publications.require_workspace_publish,
        publications.get_publication_publish_transport,
        publications.verify_and_consume_publication_activation_for_execution,
        publications.execute_confirmed_meta_publication_with_transport,
        publications.settings.real_publish_enabled,
    )

    trace = []

    async def allow_rate_limit(**kwargs):
        return None

    async def authorize(
        db,
        user,
        workspace_id,
    ):
        trace.append(
            "authorize"
        )

    def factory():
        trace.append(
            "transport"
        )

        return FakeTransport()

    async def activation_gate(
        **kwargs,
    ):
        trace.append(
            "activation"
        )

        if kwargs[
            "activation_value"
        ] != ACTIVATION:
            raise AssertionError(
                "HTTP activation bearer propagation failed"
            )

        if kwargs[
            "expected_content_hash"
        ] != CONTENT_HASH:
            raise AssertionError(
                "HTTP activation hash propagation failed"
            )

        if kwargs[
            "user_id"
        ] != USER_ID:
            raise AssertionError(
                "HTTP activation operator propagation failed"
            )

    async def execute(
        **kwargs,
    ):
        trace.append(
            "confirmation/executor"
        )

        if kwargs[
            "confirmation_value"
        ] != CONFIRMATION:
            raise AssertionError(
                "confirmation propagation failed"
            )

        if kwargs[
            "expected_content_hash"
        ] != CONTENT_HASH:
            raise AssertionError(
                "controlled hash propagation failed"
            )

        return SimpleNamespace(
            provider_post_id=(
                "mock_provider_post"
            ),
            provider_permalink=None,
        )

    try:
        publications.enforce_rate_limit = (
            allow_rate_limit
        )

        publications.require_workspace_publish = (
            authorize
        )

        publications.get_publication_publish_transport = (
            factory
        )

        publications.verify_and_consume_publication_activation_for_execution = (
            activation_gate
        )

        publications.execute_confirmed_meta_publication_with_transport = (
            execute
        )

        publications.settings.real_publish_enabled = (
            True
        )

        result = (
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID
                ),
                db=FakeDB(),
            )
        )

        if trace != [
            "authorize",
            "transport",
            "activation",
            "confirmation/executor",
        ]:
            raise AssertionError(
                f"HTTP execution ordering={trace}"
            )

        if result.status != PublicationStatus.published:
            raise AssertionError(
                "valid activated publish did not map published"
            )

        print(
            "HTTP authorization before provider factory: PASS"
        )
        print(
            "Provider factory before activation consume: PASS"
        )
        print(
            "Activation before confirmation/executor: PASS"
        )

        #
        # Activation rejection must prevent existing
        # confirmation consumption/executor entirely.
        #
        trace.clear()

        async def reject_activation(
            **kwargs,
        ):
            trace.append(
                "activation"
            )

            raise publications.ControlledPublicationActivationRejected(
                "SECRET_ACTIVATION_DETAIL"
            )

        publications.verify_and_consume_publication_activation_for_execution = (
            reject_activation
        )

        try:
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID
                ),
                db=FakeDB(),
            )
        except HTTPException as exc:
            if exc.status_code != 409:
                raise AssertionError(
                    "activation rejection HTTP status mismatch"
                )

            if (
                "SECRET_ACTIVATION_DETAIL"
                in str(
                    exc.detail
                )
            ):
                raise AssertionError(
                    "activation rejection detail exposed"
                )
        else:
            raise AssertionError(
                "activation rejection accepted"
            )

        if trace != [
            "authorize",
            "transport",
            "activation",
        ]:
            raise AssertionError(
                f"activation rejection reached executor: {trace}"
            )

        print(
            "Rejected activation -> HTTP 409: PASS"
        )
        print(
            "Rejected activation reaches confirmation/executor: NO"
        )
        print(
            "Activation rejection secret isolation: PASS"
        )

    finally:
        (
            publications.enforce_rate_limit,
            publications.require_workspace_publish,
            publications.get_publication_publish_transport,
            publications.verify_and_consume_publication_activation_for_execution,
            publications.execute_confirmed_meta_publication_with_transport,
            publications.settings.real_publish_enabled,
        ) = originals


asyncio.run(
    main()
)

print()
print(
    "v0.13E-E-C /publish activation HTTP ordering: PASS"
)
print(
    "Real Redis calls: NONE"
)
print(
    "Credential decrypt calls: NONE"
)
print(
    "Real Meta calls: NONE"
)
print(
    "Facebook posts created: NONE"
)
