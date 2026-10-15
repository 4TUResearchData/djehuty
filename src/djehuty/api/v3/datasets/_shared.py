"""Shared helpers for the v3 datasets sub-resources."""

import re
from typing import Annotated

from fastapi import Path

from djehuty.api.exceptions import NotFoundError
from djehuty.utils.convenience import html_to_plaintext

DatasetId = Annotated[
    str,
    Path(
        description=(
            "The dataset — its version-independent container UUID, or a numeric "
            "legacy id; both resolve to the same dataset."
        )
    ),
]


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


def _build_search_query(search_for, search_operator, search_scope):
    """Build a structured query and plain-text values for v3 dataset search."""
    if search_for is None:
        return None, None

    search_for = search_for.strip()
    if not search_for:
        return None, None

    search_for_raw = html_to_plaintext(search_for)
    search_tokens = re.findall(r'[^" ]+|"[^"]+"|\([^)]+\)', search_for)
    search_tokens = [token.strip('"') for token in search_tokens]

    search_query = {
        "operator": search_operator,
        "search_for": search_tokens,
        "scope": search_scope,
    }

    return search_query, search_for_raw
