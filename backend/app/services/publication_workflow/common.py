import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_generation import (
    ContentGeneration,
    ContentStatus,
)
from app.models.publication import (
    Publication,
    PublicationStatus,
    utcnow,
)
from app.models.social_account import (
    SocialAccount,
    SocialAccountStatus,
)


class PublicationWorkflowError(RuntimeError):
    pass


class PublicationNotFound(
    PublicationWorkflowError
):
    pass


class PublicationValidationError(
    PublicationWorkflowError
):
    pass


class PublicationStateError(
    PublicationWorkflowError
):
    pass


class PublicationIdempotencyConflict(
    PublicationWorkflowError
):
    pass



















