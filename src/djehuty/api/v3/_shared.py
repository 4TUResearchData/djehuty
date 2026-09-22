"""Shared OpenAPI documentation helpers for the v3 API."""


def _ok(description, example):
    """Build a 200-response entry carrying an OpenAPI example."""
    return {"description": description, "content": {"application/json": {"example": example}}}
