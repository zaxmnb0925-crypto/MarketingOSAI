import uuid

from app.core.config import settings

from app.services.publication_canary_target import (
    PublicationCanaryTargetRejected,
    require_exact_publication_canary_target,
)


def expect_rejected(
    *,
    workspace_id,
    publication_id,
):
    try:
        require_exact_publication_canary_target(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )
    except PublicationCanaryTargetRejected:
        return

    raise AssertionError(
        "canary target unexpectedly allowed"
    )


def main():
    original_workspace = (
        settings.meta_publish_canary_workspace_id
    )

    original_publication = (
        settings.meta_publish_canary_publication_id
    )

    workspace_id = uuid.uuid4()

    publication_id = uuid.uuid4()

    wrong_workspace_id = uuid.uuid4()

    wrong_publication_id = uuid.uuid4()

    try:
        #
        # Default unset must fail closed.
        #
        settings.meta_publish_canary_workspace_id = (
            None
        )

        settings.meta_publish_canary_publication_id = (
            None
        )

        expect_rejected(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )

        print(
            "Canary target unset -> fail closed: PASS"
        )

        #
        # Partial configuration must also fail closed.
        #
        settings.meta_publish_canary_workspace_id = (
            workspace_id
        )

        settings.meta_publish_canary_publication_id = (
            None
        )

        expect_rejected(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )

        settings.meta_publish_canary_workspace_id = (
            None
        )

        settings.meta_publish_canary_publication_id = (
            publication_id
        )

        expect_rejected(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )

        print(
            "Partial canary configuration -> fail closed: PASS"
        )

        #
        # Exact configuration.
        #
        settings.meta_publish_canary_workspace_id = (
            workspace_id
        )

        settings.meta_publish_canary_publication_id = (
            publication_id
        )

        #
        # Wrong Workspace.
        #
        expect_rejected(
            workspace_id=wrong_workspace_id,
            publication_id=publication_id,
        )

        print(
            "Wrong canary Workspace -> rejected: PASS"
        )

        #
        # Wrong Publication.
        #
        expect_rejected(
            workspace_id=workspace_id,
            publication_id=wrong_publication_id,
        )

        print(
            "Wrong canary Publication -> rejected: PASS"
        )

        #
        # Exact target.
        #
        require_exact_publication_canary_target(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )

        print(
            "Exact canary Workspace + Publication -> allowed: PASS"
        )

    finally:
        settings.meta_publish_canary_workspace_id = (
            original_workspace
        )

        settings.meta_publish_canary_publication_id = (
            original_publication
        )

    print(
        "Canary config restored: PASS"
    )

    print()
    print(
        "v0.13E-E-D CANARY TARGET FOUNDATION: PASS"
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
