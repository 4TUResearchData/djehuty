"""Shared helpers for the account/collections sub-resources."""

from djehuty.api.exceptions import NotFoundError


def _ok(description, example):
    """Build a 200-response entry carrying an OpenAPI example."""
    return {"description": description, "content": {"application/json": {"example": example}}}


def _find_collection(db, collection_id, account_uuid, is_published=False):
    """Return the account's collection by numeric ID or UUID, or None."""
    try:
        try:
            numeric_id = int(collection_id)
            return db.collections(
                collection_id=numeric_id, account_uuid=account_uuid, is_published=is_published
            )[0]
        except (ValueError, TypeError):
            return db.collections(
                container_uuid=str(collection_id),
                account_uuid=account_uuid,
                is_published=is_published,
            )[0]
    except (IndexError, AttributeError):
        return None


def _resolve_private_collection(db, collection_id, account_uuid):
    """Resolve a private collection or raise NotFoundError."""
    collection = _find_collection(db, collection_id, account_uuid, is_published=False)
    if collection is None:
        raise NotFoundError()
    return collection


def _editable_collection(db, collection_id, account_uuid):
    """Return the account's draft collection, drafting a published one first."""
    collection = _find_collection(db, collection_id, account_uuid, is_published=False)
    if collection is not None:
        return collection

    published = _find_collection(db, collection_id, account_uuid, is_published=True)
    if published is None:
        return None

    if db.create_draft_from_published_collection(published["container_uuid"]) is None:
        return None

    return _find_collection(db, published["container_uuid"], account_uuid, is_published=False)
