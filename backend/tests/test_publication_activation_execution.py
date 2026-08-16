import asyncio
from types import SimpleNamespace
from uuid import uuid4

import app.services.publication_activation_execution as gate

from app.services.publication_activation import (
    PublicationActivationInvalid,
)
from app.services.publication_controlled_execution import (
    ControlledPublicationContentHashMismatch,
    ControlledPublicationExecutionDisabled,
)


WORKSPACE_ID = uuid4()
PUBLICATION_ID = uuid4()
USER_ID = uuid4()

ACTIVATION = (
    "activation-execution-test-"
    + ("x" * 32)
)

CONTENT_HASH = (
    "a" * 64
)

STALE_HASH = (
    "b" * 64
)


class FakeDB:
    pass


async def main():
    originals = (
        gate.settings.real_publish_enabled,
        gate.settings.meta_publish_transport_enabled,
        gate.build_publication_meta_dry_run,
        gate.consume_and_verify_publication_activation,
    )

    trace = []

    async def dry_run(
        db,
        workspace_id,
        publication_id,
    ):
        trace.append(
            "dry-run"
        )

        return SimpleNamespace(
            content_hash=CONTENT_HASH
        )

    async def consume(
        **kwargs,
    ):
        trace.append(
            "activation"
        )

        if kwargs[
            "activation_value"
        ] != ACTIVATION:
            raise AssertionError(
                "activation bearer propagation failed"
            )

        if kwargs[
            "expected_workspace_id"
        ] != WORKSPACE_ID:
            raise AssertionError(
                "workspace binding propagation failed"
            )

        if kwargs[
            "expected_publication_id"
        ] != PUBLICATION_ID:
            raise AssertionError(
                "publication binding propagation failed"
            )

        if kwargs[
            "expected_user_id"
        ] != USER_ID:
            raise AssertionError(
                "operator binding propagation failed"
            )

        if kwargs[
            "expected_content_hash"
        ] != CONTENT_HASH:
            raise AssertionError(
                "hash binding propagation failed"
            )

    try:
        gate.build_publication_meta_dry_run = (
            dry_run
        )

        gate.consume_and_verify_publication_activation = (
            consume
        )

        #
        # Gate 1 OFF.
        #
        gate.settings.real_publish_enabled = (
            False
        )

        gate.settings.meta_publish_transport_enabled = (
            True
        )

        trace.clear()

        try:
            await gate.verify_and_consume_publication_activation_for_execution(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                activation_value=ACTIVATION,
                expected_content_hash=CONTENT_HASH,
            )
        except ControlledPublicationExecutionDisabled:
            pass
        else:
            raise AssertionError(
                "real publish OFF accepted activation"
            )

        if trace:
            raise AssertionError(
                "real publish OFF touched preflight/activation"
            )

        print(
            "Real publish OFF before activation activity: PASS"
        )

        #
        # Gate 2 OFF.
        #
        gate.settings.real_publish_enabled = (
            True
        )

        gate.settings.meta_publish_transport_enabled = (
            False
        )

        trace.clear()

        try:
            await gate.verify_and_consume_publication_activation_for_execution(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                activation_value=ACTIVATION,
                expected_content_hash=CONTENT_HASH,
            )
        except ControlledPublicationExecutionDisabled:
            pass
        else:
            raise AssertionError(
                "transport OFF accepted activation"
            )

        if trace:
            raise AssertionError(
                "transport OFF touched preflight/activation"
            )

        print(
            "Transport wiring OFF before activation activity: PASS"
        )

        #
        # Both global gates ON, but stale hash.
        #
        gate.settings.real_publish_enabled = (
            True
        )

        gate.settings.meta_publish_transport_enabled = (
            True
        )

        trace.clear()

        try:
            await gate.verify_and_consume_publication_activation_for_execution(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                activation_value=ACTIVATION,
                expected_content_hash=STALE_HASH,
            )
        except ControlledPublicationContentHashMismatch:
            pass
        else:
            raise AssertionError(
                "stale hash accepted activation"
            )

        if trace != [
            "dry-run",
        ]:
            raise AssertionError(
                f"stale hash ordering={trace}"
            )

        print(
            "Exact hash before activation GETDEL: PASS"
        )

        #
        # Invalid/misbound/replayed activation.
        #
        async def reject(
            **kwargs,
        ):
            trace.append(
                "activation"
            )

            raise PublicationActivationInvalid(
                "SECRET_ACTIVATION_INTERNAL_DETAIL"
            )

        gate.consume_and_verify_publication_activation = (
            reject
        )

        trace.clear()

        try:
            await gate.verify_and_consume_publication_activation_for_execution(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                activation_value=ACTIVATION,
                expected_content_hash=CONTENT_HASH,
            )
        except gate.ControlledPublicationActivationRejected as exc:
            if (
                "SECRET_ACTIVATION_INTERNAL_DETAIL"
                in str(exc)
            ):
                raise AssertionError(
                    "activation backend detail exposed"
                )
        else:
            raise AssertionError(
                "rejected activation accepted"
            )

        if trace != [
            "dry-run",
            "activation",
        ]:
            raise AssertionError(
                f"activation rejection ordering={trace}"
            )

        print(
            "Activation rejection fails closed: PASS"
        )
        print(
            "Activation internal detail isolation: PASS"
        )

        #
        # Valid activation.
        #
        gate.consume_and_verify_publication_activation = (
            consume
        )

        trace.clear()

        await gate.verify_and_consume_publication_activation_for_execution(
            db=FakeDB(),
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            user_id=USER_ID,
            activation_value=ACTIVATION,
            expected_content_hash=CONTENT_HASH,
        )

        if trace != [
            "dry-run",
            "activation",
        ]:
            raise AssertionError(
                f"valid activation ordering={trace}"
            )

        print(
            "Exact activation binding propagation: PASS"
        )
        print(
            "Valid activation execution gate: PASS"
        )

    finally:
        (
            gate.settings.real_publish_enabled,
            gate.settings.meta_publish_transport_enabled,
            gate.build_publication_meta_dry_run,
            gate.consume_and_verify_publication_activation,
        ) = originals


asyncio.run(
    main()
)

print()
print(
    "v0.13E-E-C activation execution gate: PASS"
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
