"""Shared helpers for the account/articles sub-resources."""

from fastapi import Depends

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import NotFoundError
from djehuty.api.permissions import enforce_collaborative_permissions


def _ok(description, example):
    """Build a 200-response entry carrying an OpenAPI example."""
    return {"description": description, "content": {"application/json": {"example": example}}}


def _resolve_private_dataset(db, dataset_id, account_uuid, permission):
    """Resolve a private dataset and enforce a collaborative permission.

    ``permission`` is a collaborative-permission name or
    :data:`djehuty.api.permissions.OWNER_ONLY`. No-op for the owner; raises
    :class:`NotFoundError` for a missing dataset and
    :class:`~djehuty.api.exceptions.ForbiddenError` for a collaborator lacking it.
    """
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
        raise NotFoundError() from None
    enforce_collaborative_permissions(db, account_uuid, dataset, "dataset", permission)
    return dataset


def require_article_permission(permission):
    """FastAPI dependency: resolve ``{dataset_id}`` and enforce ``permission``.

    ``permission`` is a collaborative-permission name or
    :data:`djehuty.api.permissions.OWNER_ONLY`. See :func:`_resolve_private_dataset`
    for the owner/404/403 contract. It runs before the route body, so routes that
    must turn a missing draft into 403/500/``[]`` resolve explicitly instead.
    """

    def dependency(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
        return _resolve_private_dataset(db, dataset_id, account["uuid"], permission)

    return dependency
