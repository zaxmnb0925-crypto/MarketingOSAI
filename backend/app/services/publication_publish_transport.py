from app.core.config import settings
from app.services.meta_publishing import (
    MetaGraphHTTPTransport,
    MetaPublishingTransport,
)


class PublicationPublishTransportUnavailable(
    RuntimeError
):
    pass


def get_publication_publish_transport(
) -> MetaPublishingTransport:
    """
    Return the production Meta publishing transport only
    when provider wiring has been explicitly enabled.

    This is intentionally independent from the higher-level
    real_publish_enabled execution kill switch.

    Required production safety model:

        real_publish_enabled
                AND
        meta_publish_transport_enabled

    The HTTP endpoint checks real_publish_enabled before this
    factory is requested. This factory then independently
    fails closed unless provider wiring is enabled.

    Constructing MetaGraphHTTPTransport performs no provider
    request. Network activity occurs only later when the
    executor invokes the injected transport.
    """

    if not settings.meta_publish_transport_enabled:
        raise PublicationPublishTransportUnavailable(
            "Real publishing transport is not configured"
        )

    return MetaGraphHTTPTransport()
