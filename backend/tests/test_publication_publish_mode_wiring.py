import sys as _publication_compat_sys
from pathlib import Path as _publication_compat_Path

_publication_compat_dir = str(
    _publication_compat_Path(
        __file__
    ).resolve().parent
)

if (
    _publication_compat_dir
    not in _publication_compat_sys.path
):
    _publication_compat_sys.path.insert(
        0,
        _publication_compat_dir,
    )

from _publication_test_compat import (
    publication_publishing_source_path,
    publication_source_paths,
    publication_source_text,
    publications,
)

from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.services.publication_publish_target_policy import (
    PublicationPublishTargetRejected,
    require_allowed_publication_publish_target,
)


API = publication_publishing_source_path().read_text()

EXEC = Path(
    "app/services/publication_activation_execution.py"
).read_text()

POLICY = Path(
    "app/services/publication_publish_target_policy.py"
).read_text()


def check(
    condition,
    message,
):
    if not condition:
        raise AssertionError(
            message
        )


def expect_rejected(
    workspace_id,
    publication_id,
):
    try:
        require_allowed_publication_publish_target(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )
    except PublicationPublishTargetRejected:
        return

    raise AssertionError(
        "target unexpectedly accepted"
    )


def static_contract():
    check(
        API.count(
            "require_allowed_publication_publish_target("
        )
        == 2,
        "API policy calls != 2",
    )

    check(
        EXEC.count(
            "require_allowed_publication_publish_target("
        )
        == 1,
        "execution policy calls != 1",
    )

    check(
        "require_exact_publication_canary_target"
        not in API,
        "legacy helper remains in API",
    )

    check(
        "require_exact_publication_canary_target"
        not in EXEC,
        "legacy helper remains in execution",
    )

    check(
        POLICY.count(
            "require_exact_publication_canary_target("
        )
        == 1,
        "policy internal canary delegation != 1",
    )

    activation = API.split(
        "async def create_publication_activation_endpoint(",
        1,
    )[1]

    check(
        "if settings.meta_publish_canary_mode_enabled:"
        in activation,
        "activation mode branch missing",
    )

    check(
        "await require_workspace_publish_activation("
        in activation,
        "CANARY owner auth missing",
    )

    check(
        "await require_workspace_publish("
        in activation,
        "NORMAL publish auth missing",
    )

    publish = API.split(
        "async def publish_publication_endpoint(",
        1,
    )[1].split(
        "@router.post(",
        1,
    )[0]

    check(
        publish.index(
            "if not settings.real_publish_enabled:"
        )
        <
        publish.index(
            "require_allowed_publication_publish_target("
        )
        <
        publish.index(
            "get_publication_publish_transport()"
        ),
        "/publish ordering changed",
    )

    check(
        activation.index(
            "if settings.meta_publish_canary_mode_enabled:"
        )
        <
        activation.index(
            "require_allowed_publication_publish_target("
        )
        <
        activation.index(
            "build_publication_meta_dry_run("
        )
        <
        activation.index(
            "create_publication_activation("
        ),
        "activation issuance ordering changed",
    )

    check(
        EXEC.index(
            "if not settings.real_publish_enabled:"
        )
        <
        EXEC.index(
            "if not settings.meta_publish_transport_enabled:"
        )
        <
        EXEC.index(
            "require_allowed_publication_publish_target("
        )
        <
        EXEC.index(
            "build_publication_meta_dry_run("
        )
        <
        EXEC.index(
            "consume_and_verify_publication_activation("
        ),
        "activation execution ordering changed",
    )

    print(
        "API policy calls: 2"
    )

    print(
        "Execution policy calls: 1"
    )

    print(
        "Policy internal exact-canary delegation: 1"
    )

    print(
        "/publish ordering: PASS"
    )

    print(
        "Activation issuance ordering: PASS"
    )

    print(
        "Activation execution ordering: PASS"
    )


def dynamic_contract():
    old_mode = (
        settings.meta_publish_canary_mode_enabled
    )

    old_workspace = (
        settings.meta_publish_canary_workspace_id
    )

    old_publication = (
        settings.meta_publish_canary_publication_id
    )

    workspace_id = uuid4()
    publication_id = uuid4()

    try:
        settings.meta_publish_canary_mode_enabled = True

        settings.meta_publish_canary_workspace_id = None
        settings.meta_publish_canary_publication_id = None

        expect_rejected(
            workspace_id,
            publication_id,
        )

        print(
            "CANARY + UNSET: REJECTED"
        )

        settings.meta_publish_canary_workspace_id = (
            workspace_id
        )

        settings.meta_publish_canary_publication_id = (
            publication_id
        )

        require_allowed_publication_publish_target(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )

        print(
            "CANARY + EXACT: ALLOWED"
        )

        settings.meta_publish_canary_mode_enabled = False

        settings.meta_publish_canary_workspace_id = None
        settings.meta_publish_canary_publication_id = None

        require_allowed_publication_publish_target(
            workspace_id=uuid4(),
            publication_id=uuid4(),
        )

        print(
            "NORMAL + UNSET: POLICY ALLOWED"
        )

    finally:
        settings.meta_publish_canary_mode_enabled = (
            old_mode
        )

        settings.meta_publish_canary_workspace_id = (
            old_workspace
        )

        settings.meta_publish_canary_publication_id = (
            old_publication
        )

    print(
        "Settings restored: PASS"
    )


static_contract()
dynamic_contract()

print()
print(
    "v0.13F STEP 2B MODE-AWARE WIRING: FULL PASS"
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
