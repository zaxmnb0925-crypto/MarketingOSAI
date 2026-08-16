"""Deterministic identities scoped to one attested integration run."""
from __future__ import annotations

import os
import re
from uuid import NAMESPACE_URL, UUID, uuid5

_PATTERN = re.compile(r"^r22-[0-9a-f]{16}$")
TEST_RUN_ID = os.environ.get("TEST_RUN_ID", "")
if not _PATTERN.fullmatch(TEST_RUN_ID):
    raise RuntimeError("TEST_RUN_ID must match the attested r22 run-id")


def integration_uuid(label: str) -> UUID:
    if not re.fullmatch(r"[a-z0-9-]+", label):
        raise RuntimeError("integration identity label is invalid")
    return uuid5(NAMESPACE_URL, f"marketingos:{TEST_RUN_ID}:{label}")


def integration_token(label: str) -> str:
    return f"{TEST_RUN_ID}-{label}"
