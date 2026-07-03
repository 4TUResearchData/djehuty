"""Shared helpers for the account/articles sub-resources."""

from djehuty.api.exceptions import NotFoundError


def _ok(description, example):
    """Build a 200-response entry carrying an OpenAPI example."""
    return {"description": description, "content": {"application/json": {"example": example}}}


def _resolve_private_dataset(db, dataset_id, account_uuid):
    """Resolve a private dataset or raise NotFoundError/ForbiddenError."""
    try:
        try:
            numeric_id = int(dataset_id)
            dataset = db.datasets(
                dataset_id=numeric_id, account_uuid=account_uuid, is_published=False
            )[0]
        except (ValueError, TypeError):
            dataset = db.datasets(
                container_uuid=str(dataset_id), account_uuid=account_uuid, is_published=False
            )[0]
    except (IndexError, AttributeError):
        raise NotFoundError()
    return dataset
