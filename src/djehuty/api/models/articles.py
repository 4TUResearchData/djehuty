"""Models for article (dataset) endpoints."""

from pydantic import BaseModel, Field

from djehuty.api.models.common import OrderDirection, OrderField, Timeline


class Author(BaseModel):
    """Author as returned in article listings."""

    id: int | None = None
    uuid: str | None = None
    full_name: str | None = None
    is_active: bool = False
    url_name: str | None = None
    orcid_id: str = ""


class ArticleSummary(BaseModel):
    """Article summary as returned by list and search endpoints.

    This matches the Figshare v2 ``articles`` response format.
    """

    id: int | None = Field(None, description="Numeric article identifier")
    uuid: str | None = Field(None, description="Container UUID")
    title: str | None = Field(
        None, description="Article title", examples=["Wind tunnel measurements"]
    )
    doi: str | None = Field(None, description="DOI", examples=["10.4121/12345678-abcd-1234"])
    handle: str | None = None
    url: str | None = Field(None, description="Canonical URL")
    published_date: str | None = Field(None, description="Publication date (ISO 8601)")
    thumb: str | None = Field(None, description="Thumbnail URL")
    defined_type: int | None = Field(None, description="Content type ID")
    defined_type_name: str | None = Field(
        None, description="Content type name", examples=["dataset"]
    )
    group_id: int | None = Field(None, description="Institutional group ID")
    url_private_api: str | None = None
    url_public_api: str | None = None
    url_private_html: str | None = None
    url_public_html: str | None = None
    timeline: Timeline = Field(default_factory=Timeline)
    resource_title: str | None = None
    resource_doi: str | None = None
    authors: list[Author] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 12345678,
                    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "title": "Wind tunnel measurements of a scaled wind turbine",
                    "doi": "10.4121/12345678-abcd-1234",
                    "published_date": "2025-06-01T12:00:00",
                    "defined_type": 3,
                    "defined_type_name": "dataset",
                    "timeline": {"posted": "2025-06-01", "firstOnline": "2025-06-02"},
                    "resource_title": None,
                    "resource_doi": None,
                }
            ]
        },
    }


class ArticleSearchRequest(BaseModel):
    """Request body for ``POST /v2/articles/search``."""

    search_for: str | list[str] | None = Field(
        None,
        max_length=1024,
        description=(
            "Search query. Supports boolean operators (AND, OR) and field-specific "
            "search with ``:field:`` syntax (e.g. ``:title:wind turbine``)."
        ),
        examples=["wind turbine measurements"],
    )
    institution: int | None = Field(None, description="Filter by institution ID")
    group: int | None = Field(None, description="Filter by group ID", alias="group_id")
    published_since: str | None = Field(
        None,
        max_length=32,
        description="ISO 8601 date. Return only articles published after this date.",
        examples=["2025-01-01"],
    )
    modified_since: str | None = Field(
        None,
        max_length=32,
        description="ISO 8601 date. Return only articles modified after this date.",
    )
    item_type: int | None = Field(None, description="Filter by content type ID")
    categories: str | None = Field(
        None,
        max_length=512,
        description="Comma-separated list of category IDs to filter by",
        examples=["13,42"],
    )
    doi: str | None = Field(None, max_length=255, description="Filter by exact DOI")
    handle: str | None = Field(None, max_length=255, description="Filter by handle")
    resource_doi: str | None = Field(None, max_length=255)
    order: OrderField = Field("published_date", description="Field to sort results by")
    order_direction: OrderDirection = Field("desc", description="Sort direction")
    page: int | None = Field(None, ge=1, description="Page number (1-based)")
    page_size: int | None = Field(None, ge=1, le=1000, description="Results per page")
    limit: int | None = Field(None, ge=1, le=1000, description="Maximum results to return")
    offset: int | None = Field(None, ge=0, description="Number of results to skip")

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [
                {
                    "search_for": "wind turbine",
                    "order": "published_date",
                    "order_direction": "desc",
                    "limit": 10,
                }
            ]
        },
    }
