from .common import (
    AsyncSession,
    ContentGeneration,
    ContentStatus,
    Publication,
    PublicationIdempotencyConflict,
    PublicationNotFound,
    PublicationStateError,
    PublicationStatus,
    PublicationValidationError,
    PublicationWorkflowError,
    SocialAccount,
    SocialAccountStatus,
    UUID,
    hashlib,
    select,
    utcnow,
)

from .integrity import (
    content_sha256,
    verify_snapshot_integrity,
)

from .locking import (
    _get_publication_for_update,
)

from .lifecycle import (
    create_publication_draft,
    approve_publication,
)

from .attempts import (
    begin_publication_attempt,
)

from .outcomes import (
    mark_publication_published,
    mark_publication_failed,
    mark_publication_execution_unknown,
)

import sys as _sys
import types as _types
from . import attempts as _attempts_module
from . import lifecycle as _lifecycle_module
from . import outcomes as _outcomes_module

class _PublicationWorkflowFacadeModule(_types.ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "_get_publication_for_update":
            _attempts_module._get_publication_for_update = value
            _lifecycle_module._get_publication_for_update = value
            _outcomes_module._get_publication_for_update = value

_sys.modules[__name__].__class__ = _PublicationWorkflowFacadeModule
