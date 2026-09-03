"""Shared helpers for the v3 datasets sub-resources."""

from djehuty.api.exceptions import NotFoundError


def _resolve_any_dataset(db, dataset_id, account=None):
    """Resolve a dataset by ID/UUID, checking auth if available."""
    account_uuid = account["uuid"] if account else None
    try:
        try:
            numeric_id = int(dataset_id)
            return db.datasets(
                dataset_id=numeric_id,
                account_uuid=account_uuid,
                is_published=None,
                is_latest=None,
                limit=1,
            )[0]
        except (ValueError, TypeError):
            return db.datasets(
                container_uuid=str(dataset_id),
                account_uuid=account_uuid,
                is_published=None,
                is_latest=None,
                limit=1,
            )[0]
    except (IndexError, AttributeError) as error:
        raise NotFoundError() from error


def _resolve_dataset(db, dataset_id, account_uuid, is_under_review=None):
    """Resolve a dataset by ID/UUID with ownership check."""
    try:
        try:
            numeric_id = int(dataset_id)
            return db.datasets(
                dataset_id=numeric_id,
                account_uuid=account_uuid,
                is_published=False,
                is_under_review=is_under_review,
            )[0]
        except (ValueError, TypeError):
            return db.datasets(
                container_uuid=str(dataset_id),
                account_uuid=account_uuid,
                is_published=False,
                is_under_review=is_under_review,
            )[0]
    except (IndexError, AttributeError) as error:
        raise NotFoundError() from error
