"""Shared OpenAPI documentation helpers for the v3 API."""

from djehuty.api.models.common import ErrorResponse


def _ok(description, example):
    """Build a 200-response entry carrying an OpenAPI example."""
    return {"description": description, "content": {"application/json": {"example": example}}}


def _err(description, example, model=ErrorResponse):
    """Build an error-response entry carrying a schema and an example."""
    entry = {"description": description, "content": {"application/json": {"example": example}}}
    if model is not None:
        entry["model"] = model
    return entry


def _req(schema):
    """Build an ``openapi_extra`` requestBody that documents a typed JSON schema.

    The route keeps its ``body: dict``/``Any`` parameter (so request validation is
    unchanged); this only deep-merges the schema into the generated OpenAPI, giving
    the Swagger "Schema" tab real fields instead of a bare object.
    """
    return {"requestBody": {"content": {"application/json": {"schema": schema}}}}
