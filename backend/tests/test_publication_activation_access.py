import asyncio
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

import app.api.publication_activation_access as access

from app.models.membership import (
    MembershipRole,
)


async def main():
    original = (
        access.require_workspace_publish
    )

    calls = []

    async def run_role(
        role,
    ):
        async def fake_publish(
            db,
            user,
            workspace_id,
        ):
            calls.append(
                role
            )

            return SimpleNamespace(
                role=role
            )

        access.require_workspace_publish = (
            fake_publish
        )

        return await access.require_workspace_publish_activation(
            object(),
            SimpleNamespace(
                id=uuid4()
            ),
            uuid4(),
        )

    try:
        owner = await run_role(
            MembershipRole.owner
        )

        if (
            owner.role
            != MembershipRole.owner
        ):
            raise AssertionError(
                "owner activation authorization failed"
            )

        for denied in (
            MembershipRole.admin,
            MembershipRole.manager,
            MembershipRole.editor,
        ):
            try:
                await run_role(
                    denied
                )
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise AssertionError(
                        "wrong activation denial status"
                    )
            else:
                raise AssertionError(
                    f"activation role unexpectedly allowed: {denied}"
                )

        if len(calls) != 4:
            raise AssertionError(
                "ordinary publish authorization was bypassed"
            )

        print(
            "Activation owner role: ALLOWED"
        )
        print(
            "Activation admin role: DENIED"
        )
        print(
            "Activation manager role: DENIED"
        )
        print(
            "Activation editor role: DENIED"
        )
        print(
            "Existing publish authorization called first: PASS"
        )
        print(
            "Activation permission narrower than PUBLISH_ROLES: PASS"
        )

    finally:
        access.require_workspace_publish = (
            original
        )


asyncio.run(
    main()
)

print()
print(
    "v0.13E-E-C activation authorization: PASS"
)
