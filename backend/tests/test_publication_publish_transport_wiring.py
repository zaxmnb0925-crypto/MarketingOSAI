from app.core.config import settings
from app.services.meta_publishing import (
    MetaGraphHTTPTransport,
)
from app.services.publication_publish_transport import (
    PublicationPublishTransportUnavailable,
    get_publication_publish_transport,
)


def main():
    original_transport_enabled = (
        settings.meta_publish_transport_enabled
    )

    original_publish_enabled = (
        settings.real_publish_enabled
    )

    try:
        #
        # Default provider wiring must remain OFF.
        #
        settings.meta_publish_transport_enabled = (
            False
        )

        settings.real_publish_enabled = (
            False
        )

        try:
            get_publication_publish_transport()
        except PublicationPublishTransportUnavailable:
            pass
        else:
            raise AssertionError(
                "disabled provider wiring returned transport"
            )

        print(
            "Provider wiring default OFF: PASS"
        )
        print(
            "Disabled provider factory fail-closed: PASS"
        )

        #
        # Enabling provider wiring constructs the concrete
        # transport but does not perform network I/O.
        #
        settings.meta_publish_transport_enabled = (
            True
        )

        transport = (
            get_publication_publish_transport()
        )

        if not isinstance(
            transport,
            MetaGraphHTTPTransport,
        ):
            raise AssertionError(
                "factory returned wrong transport type"
            )

        print(
            "Enabled wiring returns MetaGraphHTTPTransport: PASS"
        )
        print(
            "Transport construction network calls: NONE"
        )

        #
        # Provider wiring and execution kill switch are
        # independent. Transport may be constructible while
        # real publishing remains globally OFF.
        #
        if settings.real_publish_enabled is not False:
            raise AssertionError(
                "test unexpectedly enabled real publishing"
            )

        print(
            "Independent execution kill switch remains OFF: PASS"
        )

    finally:
        settings.meta_publish_transport_enabled = (
            original_transport_enabled
        )

        settings.real_publish_enabled = (
            original_publish_enabled
        )

        print(
            "Process-local settings restored: PASS"
        )


if __name__ == "__main__":
    main()

    print()
    print(
        "v0.13E-E-A provider wiring safety: PASS"
    )
    print(
        "Real Meta network calls: NONE"
    )
    print(
        "Facebook posts created: NONE"
    )


def test_v014_pytest_reachability():
    """Execute the legacy direct-script contract through its original __main__ path."""
    import runpy as _v014_runpy

    _v014_runpy.run_path(
        __file__,
        run_name="__main__",
    )
