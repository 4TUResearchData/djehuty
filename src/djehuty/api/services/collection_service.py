"""Business logic for collection operations."""

from djehuty.web import formatter
from djehuty.web.config import config


class CollectionService:
    """Service layer for collection operations."""

    def __init__(self, db):
        self.db = db

    def list_collections(
        self,
        *,
        limit=10,
        offset=0,
        order="published_date",
        order_direction="desc",
        categories=None,
        doi=None,
        handle=None,
        groups=None,
        institution=None,
        modified_since=None,
        published_since=None,
        resource_doi=None,
        search_for=None,
        is_latest=True,
        is_published=True,
        account_uuid=None,
        **kwargs,
    ) -> list[dict]:
        """Return a list of formatted collection summaries."""
        records = self.db.collections(
            limit=limit,
            offset=offset,
            order=order,
            order_direction=order_direction,
            categories=categories,
            doi=doi,
            handle=handle,
            group=groups,
            institution=institution,
            modified_since=modified_since,
            published_since=published_since,
            resource_doi=resource_doi,
            search_for=search_for,
            is_latest=is_latest,
            is_published=is_published,
            account_uuid=account_uuid,
        )
        return [
            formatter.format_collection_record({**r, "base_url": config.base_url}) for r in records
        ]

    def search_collections(
        self,
        *,
        limit=10,
        offset=0,
        order="published_date",
        order_direction="desc",
        account_uuid=None,
        **kwargs,
    ) -> tuple[list[dict], int | None]:
        """Search collections, returning results and total count."""
        records = self.db.collections(
            limit=limit,
            offset=offset,
            order=order,
            order_direction=order_direction,
            is_latest=True,
            account_uuid=account_uuid,
            **kwargs,
        )
        formatted = [
            formatter.format_collection_record({**r, "base_url": config.base_url}) for r in records
        ]
        return formatted, len(records) if records else None

    def get_collection_details(
        self, collection_id, account_uuid=None, is_latest=True, is_published=True
    ) -> dict | None:
        """Return formatted collection detail or None."""
        collection = self._resolve_collection(
            collection_id,
            account_uuid,
            is_latest,
            is_published=is_published,
        )
        if collection is None:
            return None

        collection["base_url"] = config.base_url
        collection_uri = collection["uri"]

        return formatter.format_collection_details_record(
            collection=collection,
            funding=self.db.fundings(item_uri=collection_uri, item_type="collection"),
            categories=self.db.categories(item_uri=collection_uri, limit=None),
            authors=self.db.authors(item_uri=collection_uri, item_type="collection"),
            tags=self.db.tags(item_uri=collection_uri),
            references=self.db.references(item_uri=collection_uri),
            custom_fields=self.db.custom_fields(
                item_uri=collection_uri,
                item_type="collection",
            ),
            datasets_count=self.db.collections_dataset_count(
                collection_uri=collection_uri,
            ),
        )

    def get_collection_versions(
        self, container_uuid, order="version", order_direction="desc", limit=None, offset=None
    ) -> list[dict]:
        """Return version records for a collection container."""
        container_uri = f"container:{container_uuid}"
        records = self.db.collection_versions(
            container_uri=container_uri,
            order=order,
            order_direction=order_direction,
            limit=limit,
            offset=offset,
        )
        return [formatter.format_collection_version_record(r) for r in records]

    def get_collection_datasets(self, collection_id, limit=10, offset=0) -> list[dict] | None:
        """Return datasets in a collection."""
        collection = self._resolve_collection(collection_id, is_latest=True)
        if collection is None:
            return None

        records = self.db.collection_datasets(
            container_uri=collection["container_uri"],
            limit=limit,
            offset=offset,
        )
        return [
            formatter.format_dataset_record({**r, "base_url": config.base_url}) for r in records
        ]

    def _resolve_collection(
        self, collection_id, account_uuid=None, is_latest=True, is_published=True
    ):
        """Resolve a collection by numeric ID or UUID."""
        try:
            try:
                numeric_id = int(collection_id)
                return self.db.collections(
                    collection_id=numeric_id,
                    account_uuid=account_uuid,
                    is_latest=is_latest,
                    is_published=is_published,
                )[0]
            except (ValueError, TypeError):
                return self.db.collections(
                    container_uuid=str(collection_id),
                    account_uuid=account_uuid,
                    is_latest=is_latest,
                    is_published=is_published,
                )[0]
        except (IndexError, AttributeError):
            return None
