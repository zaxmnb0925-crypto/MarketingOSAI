from uuid import uuid4

from app.core.config import settings
from app.services.publication_publish_target_policy import (
    PublicationPublishTargetRejected,
    require_allowed_publication_publish_target,
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


def main():
    original_mode = (
        settings.meta_publish_canary_mode_enabled
    )

    original_workspace = (
        settings.meta_publish_canary_workspace_id
    )

    original_publication = (
        settings.meta_publish_canary_publication_id
    )

    workspace_id = uuid4()
    publication_id = uuid4()

    wrong_workspace_id = uuid4()
    wrong_publication_id = uuid4()

    try:
        #
        # Default safety contract:
        # canary mode + targets unset => reject.
        #
        settings.meta_publish_canary_mode_enabled = True
        settings.meta_publish_canary_workspace_id = None
        settings.meta_publish_canary_publication_id = None

        expect_rejected(
            workspace_id,
            publication_id,
        )

        print(
            "Canary mode + UNSET target rejects: PASS"
        )

        #
        # Exact configured target is accepted.
        #
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
            "Canary mode + exact target accepts: PASS"
        )

        expect_rejected(
            wrong_workspace_id,
            publication_id,
        )

        expect_rejected(
            workspace_id,
            wrong_publication_id,
        )

        print(
            "Canary mode + wrong target rejects: PASS"
        )

        #
        # Normal mode deliberately removes only the exact
        # canary-target restriction.
        #
        settings.meta_publish_canary_mode_enabled = False

        settings.meta_publish_canary_workspace_id = None
        settings.meta_publish_canary_publication_id = None

        require_allowed_publication_publish_target(
            workspace_id=wrong_workspace_id,
            publication_id=wrong_publication_id,
        )

        print(
            "Normal mode + target UNSET accepts policy layer: PASS"
        )

        #
        # Re-enabling canary mode must immediately fail closed.
        #
        settings.meta_publish_canary_mode_enabled = True

        expect_rejected(
            wrong_workspace_id,
            wrong_publication_id,
        )

        print(
            "Re-enabled canary mode fails closed: PASS"
        )

    finally:
        settings.meta_publish_canary_mode_enabled = (
            original_mode
        )

        settings.meta_publish_canary_workspace_id = (
            original_workspace
        )

        settings.meta_publish_canary_publication_id = (
            original_publication
        )

    print(
        "Publishing mode policy regression: FULL PASS"
    )


if __name__ == "__main__":
    main()


def test_v014_pytest_reachability():
    """Execute the legacy direct-script contract through its original __main__ path."""
    import runpy as _v014_runpy

    _v014_runpy.run_path(
        __file__,
        run_name="__main__",
    )
