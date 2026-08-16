import inspect
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api import brands
from app.models.brand import Brand
from app.schemas.brand import (
    BrandCreate,
)


def test_brand_schema_rejects_blank_name():
    with pytest.raises(
        ValidationError
    ):
        BrandCreate(
            name=""
        )


def test_brand_serialization_preserves_workspace():
    workspace_id = uuid4()

    brand = Brand(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Alpha Coffee",
        language="zh-TW",
    )

    response = brands.serialize_brand(
        brand
    )

    assert response.workspace_id == workspace_id
    assert response.name == "Alpha Coffee"
    assert response.language == "zh-TW"


def test_brand_read_queries_are_workspace_scoped():
    for fn in (
        brands.list_brands,
        brands.get_brand,
        brands.update_brand,
        brands.delete_brand,
    ):
        source = inspect.getsource(
            fn
        )

        assert "workspace_id" in source
        assert (
            "Brand.workspace_id"
            in source
            or
            "require_workspace_"
            in source
        )
