"""Models for license endpoints."""

from pydantic import BaseModel, Field


class License(BaseModel):
    """A license that can be applied to datasets and collections."""

    value: int | None = Field(None, description="Numeric license identifier")
    name: str | None = Field(None, description="License name", examples=["CC BY 4.0"])
    url: str | None = Field(
        None,
        description="URL to the full license text",
        examples=["https://creativecommons.org/licenses/by/4.0/"],
    )
    type: str | None = Field(
        None,
        description="License type classification (djehuty extension)",
        examples=["data", "software"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "value": 1,
                    "name": "CC BY 4.0",
                    "url": "https://creativecommons.org/licenses/by/4.0/",
                    "type": "data",
                }
            ]
        },
    }
