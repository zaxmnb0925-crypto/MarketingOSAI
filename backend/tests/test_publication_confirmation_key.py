import hashlib

from app.services.publication_confirmation_store import (
    PUBLICATION_CONFIRMATION_REDIS_PREFIX,
    _key,
)


VALUE = (
    "TEST_CONFIRMATION_VALUE_"
    "DO_NOT_USE_AS_REDIS_KEY"
)

key = _key(
    VALUE
)

expected = (
    PUBLICATION_CONFIRMATION_REDIS_PREFIX
    + hashlib.sha256(
        VALUE.encode(
            "utf-8"
        )
    ).hexdigest()
)

if key != expected:
    raise AssertionError(
        "confirmation Redis key digest mismatch"
    )

if VALUE in key:
    raise AssertionError(
        "raw confirmation appeared in Redis key"
    )

if len(
    key.removeprefix(
        PUBLICATION_CONFIRMATION_REDIS_PREFIX
    )
) != 64:
    raise AssertionError(
        "Redis confirmation key hash length invalid"
    )

print(
    "Confirmation Redis key SHA-256: PASS"
)
print(
    "Raw bearer confirmation in Redis key: NO"
)
