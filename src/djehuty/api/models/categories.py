"""Models for category endpoints."""

from pydantic import BaseModel, Field


class Category(BaseModel):
    """A research category from the classification taxonomy."""

    id: int | None = Field(None, description="Numeric category identifier")
    uuid: str | None = Field(None, description="UUID of the category")
    title: str | None = Field(
        None,
        description="Category title",
        examples=["Electrical Engineering"],
    )
    parent_id: int | None = Field(None, description="Parent category ID (null for root categories)")
    parent_uuid: str | None = Field(None, description="Parent category UUID")
    path: str = Field("", description="Full path from root to this category")
    source_id: str | None = Field(None, description="Identifier from the source taxonomy")
    taxonomy_id: int | None = Field(None, description="Taxonomy system identifier")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 13,
                    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "title": "Electrical Engineering",
                    "parent_id": 2,
                    "parent_uuid": "f0e1d2c3-b4a5-6789-0fed-cba987654321",
                    "path": "Engineering / Electrical Engineering",
                    "source_id": "4009",
                    "taxonomy_id": 1,
                }
            ]
        },
    }
