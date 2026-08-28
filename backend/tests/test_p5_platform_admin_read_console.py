from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api import (
    platform_admin_access,
    platform_admin_billing,
    platform_admin_console,
)
from app.models.commercial import PaymentRecord
from app.models.workspace import Workspace
from app.services import commercial_billing


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)


class FakeResult:
    def __init__(self, *, scalar=None, values=()):
        self.scalar = scalar
        self.values = values

    def scalar_one(self):
        return self.scalar

    def scalars(self):
        return FakeScalars(self.values)


class QueueDB:
    def __init__(self, *results):
        self.results = list(results)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        if not self.results:
            raise AssertionError(f"Unexpected statement: {statement}")
        return self.results.pop(0)


def payment(workspace_id):
    now = datetime(2026, 8, 27, tzinfo=timezone.utc)
    return PaymentRecord(
        id=uuid4(),
        workspace_id=workspace_id,
        source="manual",
        method="bank",
        amount_minor=99000,
        currency="TWD",
        status="pending",
        received_at=now,
        confirmed_at=None,
        confirmed_by_admin_user_id=None,
        external_reference=None,
        customer_note=None,
        internal_note=None,
        idempotency_key="p5-read",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_platform_admin_me_exposes_only_safe_identity_fields():
    user = SimpleNamespace(
        id=uuid4(),
        email="admin@example.com",
        full_name="Billing Admin",
    )
    response = await platform_admin_console.platform_admin_me(
        current_user=user,
        admin=SimpleNamespace(role="billing_admin"),
    )
    assert response.user_id == user.id
    assert response.email == user.email
    assert response.role == "billing_admin"
    assert set(response.model_dump()) == {
        "user_id",
        "email",
        "full_name",
        "role",
    }


@pytest.mark.asyncio
async def test_platform_workspace_list_is_paginated_and_read_only():
    workspace = Workspace(
        id=uuid4(),
        name="Alpha",
        slug="alpha",
        created_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
    )
    db = QueueDB(
        FakeResult(scalar=1),
        FakeResult(values=[workspace]),
    )
    response = await platform_admin_console.read_platform_workspaces(
        q=" Alpha ",
        limit=25,
        offset=0,
        admin=SimpleNamespace(role="support"),
        db=db,
    )
    assert response.total == 1
    assert response.limit == 25
    assert response.items[0].id == workspace.id
    assert len(db.statements) == 2


@pytest.mark.asyncio
async def test_payment_list_is_workspace_scoped_and_paginated():
    workspace_id = uuid4()
    record = payment(workspace_id)
    db = QueueDB(
        FakeResult(scalar=1),
        FakeResult(values=[record]),
    )
    items, total = await commercial_billing.list_payments(
        db,
        workspace_id,
        status="pending",
        limit=10,
        offset=5,
    )
    assert items == [record]
    assert total == 1
    for statement in db.statements:
        compiled = str(statement)
        assert "payment_records.workspace_id" in compiled


@pytest.mark.asyncio
async def test_payment_list_handler_uses_payment_read_boundary(monkeypatch):
    workspace_id = uuid4()
    record = payment(workspace_id)

    async def fake_list(db, scoped_workspace_id, **kwargs):
        assert scoped_workspace_id == workspace_id
        assert kwargs == {
            "status": "pending",
            "limit": 20,
            "offset": 0,
        }
        return [record], 1

    monkeypatch.setattr(
        platform_admin_billing,
        "list_payments",
        fake_list,
    )
    response = await platform_admin_billing.read_payments(
        workspace_id=workspace_id,
        status_filter="pending",
        limit=20,
        offset=0,
        admin=SimpleNamespace(role="support"),
        db=object(),
    )
    assert response.total == 1
    assert response.items[0].workspace_id == workspace_id


def test_p5_routes_are_registered_with_read_dependencies():
    from app.main import app

    openapi_paths = app.openapi()["paths"]
    assert "get" in openapi_paths["/api/platform-admin/me"]
    assert "get" in openapi_paths["/api/platform-admin/workspaces"]
    payment_path = (
        "/api/platform-admin/workspaces/"
        "{workspace_id}/payments"
    )
    assert "get" in openapi_paths[payment_path]

    console_routes = {
        route.path: route
        for route in platform_admin_console.router.routes
    }
    billing_routes = {
        route.path: route
        for route in platform_admin_billing.router.routes
    }
    for path in (
        "/api/platform-admin/me",
        "/api/platform-admin/workspaces",
    ):
        dependencies = {
            dependency.call
            for dependency in console_routes[path].dependant.dependencies
        }
        assert platform_admin_access.require_platform_admin_read in dependencies

    payment_dependencies = {
        dependency.call
        for dependency in billing_routes[payment_path].dependant.dependencies
    }
    assert (
        platform_admin_access.require_platform_admin_payment_read
        in payment_dependencies
    )
