import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import (
    brands,
    content,
    credits,
    social_accounts,
    subscriptions,
)
from app.api.workspace_access import (
    require_workspace_membership,
    require_workspace_write,
)
from app.models.membership import (
    MembershipRole,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class FakeDB:
    def __init__(self, value):
        self.value = value

    async def execute(self, *args, **kwargs):
        return FakeResult(
            self.value
        )


@pytest.mark.asyncio
async def test_non_member_is_rejected():
    user = SimpleNamespace(
        id=uuid4()
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await require_workspace_membership(
            FakeDB(None),
            user,
            uuid4(),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_write_workspace():
    user = SimpleNamespace(
        id=uuid4()
    )

    membership = SimpleNamespace(
        role=MembershipRole.viewer
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await require_workspace_write(
            FakeDB(membership),
            user,
            uuid4(),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_write_workspace():
    user = SimpleNamespace(
        id=uuid4()
    )

    membership = SimpleNamespace(
        role=MembershipRole.owner
    )

    result = await require_workspace_write(
        FakeDB(membership),
        user,
        uuid4(),
    )

    assert result is membership


def test_workspace_routes_are_guarded():
    functions = [
        brands.list_brands,
        brands.create_brand,
        brands.get_brand,
        brands.update_brand,
        brands.delete_brand,
        content.preview_content,
        content.list_content_generations,
        content.generate_content,
        social_accounts.list_social_accounts,
        social_accounts.get_social_account,
        social_accounts.update_social_account,
        social_accounts.delete_social_account,
        subscriptions.get_workspace_subscription,
        subscriptions.change_workspace_plan,
    ]

    gates = (
        "require_workspace_membership",
        "require_workspace_write",
        "require_workspace_publish",
        "require_workspace_delete",
    )

    for fn in functions:
        source = inspect.getsource(
            fn
        )

        assert "workspace_id" in source, (
            f"{fn.__name__} missing workspace binding"
        )

        assert any(
            gate in source
            for gate in gates
        ), (
            f"{fn.__name__} missing workspace access gate"
        )


def test_platform_billing_routes_use_platform_not_workspace_authority():
    from app.api import platform_admin_billing

    functions = [
        platform_admin_billing.record_manual_payment,
        platform_admin_billing.read_payment,
        platform_admin_billing.confirm_payment,
        platform_admin_billing.read_subscription,
        platform_admin_billing.suspend_workspace_subscription,
        platform_admin_billing.transition_workspace_subscription_to_free,
    ]
    for fn in functions:
        source = inspect.getsource(fn)
        assert "workspace_id" in source
        assert "require_platform_admin_" in source
        assert "require_workspace_" not in source
