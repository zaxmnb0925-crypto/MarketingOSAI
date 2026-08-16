from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.publication import (
    PublicationStatus,
)

from app.models.publication_reconciliation import (
    PublicationReconciliationDecision,
)


class PublicationDraftCreate(BaseModel):
    content_generation_id: UUID
    social_account_id: UUID

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
    )

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Idempotency key cannot be blank"
            )

        return cleaned


class PublicationResponse(BaseModel):
    id: UUID
    workspace_id: UUID

    brand_id: UUID | None = None
    content_generation_id: UUID | None = None
    social_account_id: UUID | None = None
    created_by_user_id: UUID | None = None

    status: PublicationStatus

    platform: str
    target_account_id: str
    target_account_name: str | None = None

    content_snapshot: str
    content_hash: str

    idempotency_key: str

    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None

    publish_triggered_by_user_id: UUID | None = None
    publish_triggered_at: datetime | None = None

    publish_attempts: int

    provider_post_id: str | None = None
    provider_permalink: str | None = None

    last_error: str | None = None
    published_at: datetime | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }



class PublicationDryRunResponse(BaseModel):
    provider: str
    platform: str
    action: str

    target_account_id: str
    endpoint_path: str

    content_hash: str
    content_length: int


class PublicationConfirmationResponse(BaseModel):
    publication_id: UUID

    #
    # Returned once to the authorized operator.
    # repr=False reduces accidental representation in
    # application/debug objects. It is intentionally not
    # a Publication database field.
    #
    confirmation: str = Field(
        min_length=32,
        max_length=256,
        repr=False,
    )

    expires_in: int = Field(
        ge=1,
        le=600,
    )

    content_hash: str = Field(
        min_length=64,
        max_length=64,
    )


class PublicationPublishRequest(BaseModel):
    activation: str = Field(
        min_length=32,
        max_length=256,
        repr=False,
    )
    #
    # Opaque one-time bearer confirmation.
    # Never normalize, trim or echo this value.
    #
    confirmation: str = Field(
        min_length=32,
        max_length=256,
        repr=False,
    )

    #
    # The client must explicitly submit the exact content
    # hash it just confirmed.
    #
    content_hash: str = Field(
        min_length=64,
        max_length=64,
    )

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(
        cls,
        value: str,
    ) -> str:
        if (
            len(value) != 64
            or any(
                char not in "0123456789abcdef"
                for char in value
            )
        ):
            raise ValueError(
                "Content hash must be lowercase SHA-256"
            )

        return value


class PublicationPublishResponse(BaseModel):
    publication_id: UUID
    status: PublicationStatus

    provider_post_id: str | None = None
    provider_permalink: str | None = None

    reconciliation_required: bool = False

class PublicationActivationResponse(BaseModel):
    publication_id: UUID
    activation: str = Field(
        min_length=32,
        max_length=256,
        repr=False,
    )
    expires_in: int = Field(
        ge=1,
        le=600,
    )
    content_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )



class PublicationReconciliationRequest(BaseModel):
    decision: PublicationReconciliationDecision

    publish_attempt_number: int = Field(ge=1)

    idempotency_key: str = Field(
        min_length=1,
        max_length=128,
    )

    evidence_note: str = Field(
        min_length=1,
        max_length=2000,
    )

    provider_post_id: str | None = Field(
        default=None,
        max_length=255,
    )

    provider_permalink: str | None = Field(
        default=None,
        max_length=2048,
    )

    @field_validator(
        "idempotency_key",
        "evidence_note",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Value cannot be blank"
            )

        return cleaned

    @field_validator(
        "provider_post_id",
        "provider_permalink",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Optional provider value cannot be blank"
            )

        return cleaned

    @model_validator(mode="after")
    def validate_decision_evidence(self):
        published = (
            self.decision
            == PublicationReconciliationDecision.confirmed_published
        )

        if published:
            if self.provider_post_id is None:
                raise ValueError(
                    "confirmed_published requires provider_post_id"
                )
        elif (
            self.provider_post_id is not None
            or self.provider_permalink is not None
        ):
            raise ValueError(
                "Provider post fields are only valid "
                "for confirmed_published"
            )

        return self


class PublicationReconciliationResponse(BaseModel):
    id: UUID
    publication_id: UUID
    workspace_id: UUID

    operator_user_id: UUID | None = None

    decision: PublicationReconciliationDecision

    publish_attempt_number: int
    idempotency_key: str

    provider_post_id: str | None = None
    provider_permalink: str | None = None

    evidence_note: str
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class PublicationReconciliationResultResponse(BaseModel):
    reconciliation: PublicationReconciliationResponse

    publication_status: PublicationStatus
    reconciliation_required: bool
