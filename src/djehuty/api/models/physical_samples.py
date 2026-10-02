"""Pydantic models for the v3 physical-samples (IGSN) API.

The endpoints return formatter output verbatim via ``JSONResponse`` (AS-IS with
the legacy handlers), so these models document the response/request shapes for
the OpenAPI schema rather than gate serialization.
"""

from pydantic import BaseModel, Field


class PhysicalSampleRecord(BaseModel):
    """A physical sample metadata record (formatter.format_physical_sample_record)."""

    uuid: str | None = Field(None, description="UUID of the physical sample record.")
    title: str | None = Field(None, description="Title of the physical sample.")
    abstract: str | None = Field(None, description="Abstract or description (may contain HTML).")
    methods: str | None = Field(None, description="Methods used to collect or produce the sample.")
    resource_type: str | None = Field(None, description="Type of physical resource (e.g. Rock).")
    subject: str | None = Field(None, description="Subject classification.")
    last_modified: str | None = Field(None, description="Timestamp of the last modification.")

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


class PhysicalSampleCreatorRecord(BaseModel):
    """A creator/author record (formatter.format_author_record_v3)."""

    uuid: str | None = Field(None, description="UUID of the creator.")
    first_name: str | None = Field(None, description="First name.")
    last_name: str | None = Field(None, description="Last name.")
    full_name: str | None = Field(None, description="Full name.")
    email: str | None = Field(None, description="E-mail address (only for editable creators).")
    orcid: str | None = Field(None, description="ORCID identifier.")
    is_editable: bool | None = Field(None, description="Whether the caller may edit this creator.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "uuid": "07d6e6ce-b1bf-43ca-86e6-7a3ab8bc8416",
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "full_name": "Ada Lovelace",
                    "email": None,
                    "orcid": None,
                    "is_editable": True,
                }
            ]
        }
    }


class PhysicalSampleDateRecord(BaseModel):
    """A date entry (formatter.format_physical_sample_date_record)."""

    uuid: str | None = Field(None, description="UUID of the date entry.")
    type: str | None = Field(None, description="Date type (e.g. Collected, Created, Issued).")
    date: str | None = Field(None, description="The date, or the start of a range.")
    date_end: str | None = Field(None, description="End of the date range, if any.")
    created_date: str | None = Field(None, description="When this date entry was created.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "uuid": "b6f8d3c1-2b4e-4c6a-8d1f-3e5b7c9a0d2f",
                    "type": "Collected",
                    "date": "2010-11-02",
                    "date_end": None,
                    "created_date": "2026-07-03T10:48:50",
                }
            ]
        }
    }


class PhysicalSampleRelatedResourceRecord(BaseModel):
    """A related resource (formatter.format_physical_sample_related_resource_record)."""

    uuid: str | None = Field(None, description="UUID of the related-resource entry.")
    url: str | None = Field(None, description="Identifier of the related resource (DOI/IGSN/URL).")
    relation: str | None = Field(
        None, description="Relation label as returned (e.g. Is derived from)."
    )
    type: str | None = Field(None, description="Identifier type label as returned (e.g. IGSN).")
    created_date: str | None = Field(None, description="When this entry was created.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "uuid": "d1e2f3a4-5b6c-7d8e-9f0a-1b2c3d4e5f6a",
                    "url": "10.4121/related-dataset",
                    "relation": "Is derived from",
                    "type": "IGSN",
                    "created_date": "2026-07-03T10:48:50",
                }
            ]
        }
    }


class PrivateLinkRecord(BaseModel):
    """A private link (formatter.format_private_links_record)."""

    id: str | None = Field(None, description="Private-link token.")
    is_active: bool | None = Field(None, description="Whether the link is currently active.")
    expires_date: str | None = Field(None, description="Expiry date, or null for no expiry.")

    model_config = {
        "json_schema_extra": {
            "examples": [{"id": "9c8b7a6d5e4f", "is_active": True, "expires_date": None}]
        }
    }


class ReorderCreatorsRequest(BaseModel):
    """Body for reordering a creator up or down."""

    author: str = Field(..., description="The creator's UUID.")
    direction: str = Field(..., description="'up' or 'down'.")

    model_config = {
        "json_schema_extra": {
            "examples": [{"author": "07d6e6ce-b1bf-43ca-86e6-7a3ab8bc8416", "direction": "up"}]
        }
    }
