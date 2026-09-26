"""Pydantic models for the v3 physical-samples (IGSN) API.

The endpoints return formatter output verbatim via ``JSONResponse`` (AS-IS with
the legacy handlers), so these models document the response/request shapes for
the OpenAPI schema rather than gate serialization.
"""

from pydantic import BaseModel, Field


class PhysicalSampleRecord(BaseModel):
    """A physical sample metadata record (formatter.format_physical_sample_record)."""

    uuid: str | None = None
    title: str | None = None
    abstract: str | None = None
    methods: str | None = None
    resource_type: str | None = None
    subject: str | None = None
    last_modified: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "uuid": "27e6a01d-3f09-4d90-ae02-1d749ae9efb8",
                    "title": "Basalt core sample BR-2025-014",
                    "abstract": "<p>Drill core recovered off the coast of Texel.</p>",
                    "methods": None,
                    "resource_type": "Rock",
                    "subject": None,
                    "last_modified": "2026-07-03T10:48:50",
                }
            ]
        }
    }


class PhysicalSampleDateRecord(BaseModel):
    """A date entry (formatter.format_physical_sample_date_record)."""

    uuid: str | None = None
    type: str | None = None
    date: str | None = None
    date_end: str | None = None
    created_date: str | None = None


class PhysicalSampleRelatedResourceRecord(BaseModel):
    """A related resource (formatter.format_physical_sample_related_resource_record)."""

    uuid: str | None = None
    url: str | None = None
    relation: str | None = None
    type: str | None = None
    created_date: str | None = None


class PrivateLinkRecord(BaseModel):
    """A private link (formatter.format_private_links_record)."""

    id: str | None = None
    is_active: bool | None = None
    expires_date: str | None = None


class ReorderCreatorsRequest(BaseModel):
    """Body for reordering a creator up or down."""

    author: str = Field(..., description="The creator's UUID.")
    direction: str = Field(..., description="'up' or 'down'.")

    model_config = {
        "json_schema_extra": {
            "examples": [{"author": "07d6e6ce-b1bf-43ca-86e6-7a3ab8bc8416", "direction": "up"}]
        }
    }
