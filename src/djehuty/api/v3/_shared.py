"""Shared OpenAPI documentation helpers for the v3 API."""


def _ok(description, example):
    """Build a 200-response entry carrying an OpenAPI example."""
    return {"description": description, "content": {"application/json": {"example": example}}}


def _err(description, example):
    """Build an error-response entry carrying an OpenAPI example."""
    return {"description": description, "content": {"application/json": {"example": example}}}


def _req(schema):
    """Build an ``openapi_extra`` requestBody that documents a typed JSON schema.

    The route keeps its ``body: dict``/``Any`` parameter (so request validation is
    unchanged); this only deep-merges the schema into the generated OpenAPI, giving
    the Swagger "Schema" tab real fields instead of a bare object.
    """
    return {"requestBody": {"content": {"application/json": {"schema": schema}}}}
