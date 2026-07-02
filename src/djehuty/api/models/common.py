"""Common models shared across API versions."""

from typing import Literal

from pydantic import BaseModel, Field


class Timeline(BaseModel):
    """Publication timeline for datasets and collections."""

    posted: str | None = None
    firstOnline: str | None = Field(None, alias="firstOnline")
    revision: str | None = None
    submission: str | None = None
    publisherPublication: str | None = None

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [
                {
                    "posted": "2025-03-15",
                    "firstOnline": "2025-03-16",
                    "revision": None,
                }
            ]
        },
    }


class ErrorResponse(BaseModel):
    """Standard error response."""

    message: str = Field(..., description="Human-readable error description")
    code: str = Field(..., description="Machine-readable error code")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Missing required value for 'title'.",
                    "code": "MissingRequiredField",
                }
            ]
        },
    }


OrderField = Literal[
    "published_date",
    "modified_date",
    "created_date",
    "title",
    "defined_type",
    "group_id",
    "size",
]

OrderDirection = Literal["asc", "desc"]
