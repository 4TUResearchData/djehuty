"""Shared helpers for the v3 collections sub-resources."""

from djehuty.api.exceptions import NotFoundError


def _resolve_collection_for_owner(db, collection_id: str, account_uuid: str) -> dict:
    """Resolve a draft collection owned by ``account_uuid`` or raise 404."""
    try:
        try:
            numeric_id = int(collection_id)
            return db.collections(
                collection_id=numeric_id,
                account_uuid=account_uuid,
                is_published=False,
            )[0]
        except (ValueError, TypeError):
            return db.collections(
                container_uuid=str(collection_id),
                account_uuid=account_uuid,
                is_published=False,
            )[0]
    except (IndexError, AttributeError) as error:
        raise NotFoundError() from error
