import inspect
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api import content
from app.models.brand import Brand
from app.models.content_generation import (
    ContentPlatform,
)
from app.schemas.content import (
    ContentPreviewRequest,
)
from app.services.content_prompt import (
    build_brand_prompt,
    detect_forbidden_words,
)


def test_content_schema_rejects_empty_topic():
    platform = list(
        ContentPlatform
    )[0]

    with pytest.raises(
        ValidationError
    ):
        ContentPreviewRequest(
            platform=platform,
            topic="",
        )


def test_brand_prompt_contains_brand_and_topic():
    platform = list(
        ContentPlatform
    )[0]

    brand = Brand(
        id=uuid4(),
        workspace_id=uuid4(),
        name="Alpha Coffee",
        language="zh-TW",
        tone="professional",
    )

    prompt = build_brand_prompt(
        brand,
        platform,
        "Summer coffee campaign",
        None,
    )

    assert "Alpha Coffee" in prompt
    assert "Summer coffee campaign" in prompt


def test_forbidden_word_detection():
    hits = detect_forbidden_words(
        "This message contains forbidden text.",
        "forbidden",
    )

    assert any(
        str(hit).lower()
        == "forbidden"
        for hit in hits
    )


def test_content_brand_lookup_is_workspace_scoped():
    source = inspect.getsource(
        content.get_brand_for_workspace
    )

    assert "workspace_id" in source
    assert "brand_id" in source
    assert "Brand.workspace_id" in source
