"""Models for collection endpoints."""

from pydantic import BaseModel, Field

from djehuty.api.models.common import OrderDirection, OrderField, Timeline


class CollectionSummary(BaseModel):
    """Collection summary as returned by list endpoints."""

    id: int | None = Field(None, description="Numeric collection identifier")
    uuid: str | None = Field(None, description="Container UUID")
    title: str | None = Field(None, description="Collection title")
    doi: str | None = Field(None, description="DOI")
    handle: str | None = None
    url: str | None = None
    published_date: str | None = None
    thumb: str | None = None
    group_id: int | None = None
    url_private_api: str | None = None
    url_public_api: str | None = None
    url_private_html: str | None = None
    url_public_html: str | None = None
    timeline: Timeline = Field(default_factory=Timeline)
    resource_title: str | None = None
    resource_doi: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 9876543,
                    "uuid": "f1e2d3c4-b5a6-7890-fedc-ba0987654321",
                    "title": "Wind energy research data collection",
                    "doi": "10.4121/9876543-fedc-ba09",
                    "published_date": "2025-04-01T10:00:00",
                }
            ]
        },
    }


class CollectionVersion(BaseModel):
    """A version record for a collection."""

    version: int | None = None
    url: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [{"version": 1, "url": "https://data.4tu.nl/v2/collections/123/versions/1"}]
        },
    }


class CollectionSearchRequest(BaseModel):
    """Request body for ``POST /v2/collections/search``."""

    search_for: str | list[str] | None = Field(None, max_length=1024)
    institution: int | None = None
    group: int | None = Field(None, alias="group_id")
    published_since: str | None = Field(None, max_length=32)
    modified_since: str | None = Field(None, max_length=32)
    categories: str | None = Field(None, max_length=512)
    doi: str | None = Field(None, max_length=255)
    handle: str | None = Field(None, max_length=255)
    resource_doi: str | None = Field(None, max_length=255)
    order: OrderField = "published_date"
    order_direction: OrderDirection = "desc"
    page: int | None = Field(None, ge=1)
    page_size: int | None = Field(None, ge=1, le=1000)
    limit: int | None = Field(None, ge=1, le=1000)
    offset: int | None = Field(None, ge=0)

    model_config = {"populate_by_name": True}
