from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.social_account import (
    SocialAccountStatus,
    SocialPlatform,
)


class SocialAccountBase(BaseModel):
    platform: SocialPlatform

    brand_id: UUID | None = None

    platform_account_id: (
        str | None
    ) = None

    account_name: str | None = None

    username: str | None = None

    profile_url: str | None = None

    scopes: str | None = None


class SocialAccountCreate(
    SocialAccountBase
):
    pass


class SocialAccountUpdate(
    BaseModel
):
    brand_id: UUID | None = None

    account_name: str | None = None

    username: str | None = None

    profile_url: str | None = None

    is_active: bool | None = None


class SocialAccountResponse(
    SocialAccountBase
):
    id: UUID

    workspace_id: UUID

    status: SocialAccountStatus

    token_expires_at: (
        datetime | None
    ) = None

    last_synced_at: (
        datetime | None
    ) = None

    last_error: str | None = None

    is_active: bool

    created_at: datetime

    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }



class SocialAccountQuotaResponse(BaseModel):
    plan_code: str
    used: int
    limit: int | None = None
    remaining: int | None = None
