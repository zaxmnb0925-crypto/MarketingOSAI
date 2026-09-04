import inspect

import pytest
from pydantic import ValidationError

from app.api import auth
from app.schemas.auth import (
    RegisterRequest,
    TokenResponse,
)


def test_normalize_email_is_case_and_space_stable():
    assert (
        auth.normalize_email(
            "  Owner@Example.COM "
        )
        == "owner@example.com"
    )


def test_slugify_produces_stable_workspace_slug():
    value = auth.slugify(
        " Alpha Coffee "
    )

    assert value
    assert value == value.lower()
    assert " " not in value
    assert "alpha" in value
    assert "coffee" in value


def test_registration_schema_enforces_password_floor():
    with pytest.raises(
        ValidationError
    ):
        RegisterRequest(
            email="owner@example.com",
            password="short",
            full_name="Owner",
            workspace_name="Alpha",
        )


@pytest.mark.parametrize(
    "field",
    ("full_name", "workspace_name"),
)
def test_registration_schema_rejects_blank_names(field):
    values = {
        "email": "owner@example.com",
        "password": "secure-password",
        "full_name": "Owner",
        "workspace_name": "Alpha",
    }
    values[field] = "   "

    with pytest.raises(ValidationError):
        RegisterRequest(**values)


def test_registration_contract_creates_workspace_membership():
    source = inspect.getsource(
        auth.register
    )

    assert "Workspace(" in source
    assert "Membership(" in source
    assert "workspace_id" in source
    assert "MembershipRole." in source


def test_token_response_contract_contains_both_tokens():
    response = TokenResponse(
        access_token="access",
        refresh_token="refresh",
        expires_in=3600,
    )

    assert response.access_token == "access"
    assert response.refresh_token == "refresh"
    assert response.token_type == "bearer"


def test_registration_provisions_free_subscription_in_same_transaction():
    source = inspect.getsource(auth.register)
    assert "provision_free_subscription" in source
    assert source.index("provision_free_subscription") < source.index(
        "await db.commit()"
    )
    assert "await db.rollback()" in source
    assert "commit=False" in source
    assert source.count("await db.commit()") == 1


def test_registration_is_rate_limited_and_handles_unique_races():
    source = inspect.getsource(auth.register)

    assert 'scope="register"' in source
    assert "normalized_login_identifier_hash" in source
    assert "limit=5" in source
    assert "window_seconds=3600" in source
    assert "except IntegrityError" in source
    assert "status.HTTP_409_CONFLICT" in source


def test_refresh_rotation_locks_consumed_token_before_revocation():
    source = inspect.getsource(auth.refresh)

    assert ".with_for_update()" in source
    assert source.index(".with_for_update()") < source.index(
        "stored.revoked = True"
    )
    assert source.count("await db.commit()") == 1
