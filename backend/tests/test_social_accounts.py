import inspect

from app.api import social_accounts
from app.models.social_account import (
    SocialAccount,
)
from app.schemas.social_account import (
    SocialAccountResponse,
    SocialAccountUpdate,
)


def field_names(model):
    fields = getattr(
        model,
        "model_fields",
        None,
    )

    if fields is None:
        fields = getattr(
            model,
            "__fields__",
        )

    return set(
        fields.keys()
    )


def test_provider_tokens_are_not_response_fields():
    response_fields = field_names(
        SocialAccountResponse
    )

    update_fields = field_names(
        SocialAccountUpdate
    )

    assert (
        "access_token_ciphertext"
        not in response_fields
    )

    assert (
        "refresh_token_ciphertext"
        not in response_fields
    )

    assert (
        "access_token"
        not in response_fields
    )

    assert (
        "refresh_token"
        not in response_fields
    )

    assert (
        "access_token_ciphertext"
        not in update_fields
    )

    assert (
        "refresh_token_ciphertext"
        not in update_fields
    )


def test_model_keeps_tokens_ciphertext_only():
    assert hasattr(
        SocialAccount,
        "access_token_ciphertext",
    )

    assert hasattr(
        SocialAccount,
        "refresh_token_ciphertext",
    )

    assert not hasattr(
        SocialAccount,
        "access_token",
    )

    assert not hasattr(
        SocialAccount,
        "refresh_token",
    )


def test_social_account_lookup_is_workspace_scoped():
    source = inspect.getsource(
        social_accounts.get_social_account_or_404
    )

    assert "social_account_id" in source
    assert "workspace_id" in source
    assert "SocialAccount.workspace_id" in source


def test_brand_assignment_is_workspace_scoped():
    source = inspect.getsource(
        social_accounts.validate_brand_workspace
    )

    assert "brand_id" in source
    assert "workspace_id" in source
    assert "Brand.workspace_id" in source
