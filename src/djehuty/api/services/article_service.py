"""Business logic for article (dataset) operations.

This service wraps ``database.SparqlInterface`` and ``formatter`` so
that both the legacy Werkzeug handlers and the new FastAPI endpoints
can share the same logic.
"""

from djehuty.utils.convenience import value_or
from djehuty.web import formatter
from djehuty.web.config import config


class ArticleService:
    """Service layer for article/dataset operations."""

    def __init__(self, db):
        self.db = db

    def list_articles(
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
        item_type=None,
        modified_since=None,
        published_since=None,
        resource_doi=None,
        search_for=None,
        is_latest=True,
        is_published=True,
        account_uuid=None,
        **kwargs,
    ) -> list[dict]:
        """Return a list of formatted article summaries."""
        records = self.db.datasets(
            limit=limit,
            offset=offset,
            order=order,
            order_direction=order_direction,
            categories=categories,
            doi=doi,
            handle=handle,
            groups=groups,
            institution=institution,
            item_type=item_type,
            modified_since=modified_since,
            account_uuid=account_uuid,
            is_published=is_published,
            published_since=published_since,
            resource_doi=resource_doi,
            search_for=search_for,
            is_latest=is_latest,
        )
        return [
            formatter.format_dataset_record({**r, "base_url": config.base_url}) for r in records
        ]

    def search_articles(
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
        item_type=None,
        modified_since=None,
        published_since=None,
        resource_doi=None,
        search_for=None,
        **kwargs,
    ) -> tuple[list[dict], int | None]:
        """Search articles, returning results and total count.

        Returns
        -------
        tuple
            (list of formatted records, total count or None)
        """
        records = self.db.datasets(
            limit=limit,
            offset=offset,
            order=order,
            order_direction=order_direction,
            categories=categories,
            doi=doi,
            handle=handle,
            groups=groups,
            institution=institution,
            item_type=item_type,
            modified_since=modified_since,
            published_since=published_since,
            resource_doi=resource_doi,
            search_for=search_for,
            is_latest=True,
        )

        for dataset in records:
            dataset["authors"] = self.db.authors(
                item_uri=dataset["uri"],
                is_published=True,
                item_type="dataset",
                limit=10000,
            )

        formatted = [
            formatter.format_dataset_record({**r, "base_url": config.base_url}) for r in records
        ]

        total_count = None
        if records:
            count_result = self.db.datasets(
                limit=limit,
                offset=offset,
                order=order,
                order_direction=order_direction,
                categories=categories,
                doi=doi,
                handle=handle,
                groups=groups,
                institution=institution,
                item_type=item_type,
                modified_since=modified_since,
                published_since=published_since,
                resource_doi=resource_doi,
                search_for=search_for,
                is_latest=True,
                return_count=True,
            )
            total_count = value_or(count_result, 0, {"datasets": 0}).get("datasets", 0)

        return formatted, total_count

    def get_article_details(
        self, dataset_id, account_uuid=None, is_latest=False, is_published=True
    ) -> dict | None:
        """Return formatted article detail or None."""
        dataset = self._resolve_dataset(
            dataset_id, account_uuid, is_latest, is_published=is_published
        )
        if dataset is None:
            return None

        dataset["base_url"] = config.base_url
        dataset_uri = dataset["uri"]

        return formatter.format_dataset_details_record(
            dataset=dataset,
            authors=self.db.authors(item_uri=dataset_uri, item_type="dataset"),
            files=self.db.dataset_files(dataset_uri=dataset_uri),
            custom_fields=self.db.custom_fields(item_uri=dataset_uri, item_type="dataset"),
            tags=self.db.tags(item_uri=dataset_uri),
            categories=self.db.categories(item_uri=dataset_uri, limit=None),
            funding=self.db.fundings(item_uri=dataset_uri, item_type="dataset"),
            references=self.db.references(item_uri=dataset_uri),
        )

    def get_article_versions(
        self, container_uuid, order="version", order_direction="desc", limit=None, offset=None
    ) -> list[dict]:
        """Return version records for a dataset container."""
        container_uri = f"container:{container_uuid}"
        records = self.db.dataset_versions(
            container_uri=container_uri,
            order=order,
            order_direction=order_direction,
            limit=limit,
            offset=offset,
        )
        return [formatter.format_dataset_version_record(r) for r in records]

    def get_article_files(self, dataset_id, account_uuid=None) -> list[dict] | None:
        """Return files for a dataset, or None if dataset not found."""
        dataset = self._resolve_dataset(dataset_id, account_uuid, is_latest=True)
        if dataset is None:
            return None

        files = self.db.dataset_files(dataset_uri=dataset["uri"])
        return [formatter.format_file_for_dataset_record(f) for f in files]

    def get_article_version_details(self, dataset_id, version) -> dict | None:
        """Return formatted article details for a specific published version."""
        dataset = self._resolve_dataset(dataset_id, is_published=True, version=version)
        if dataset is None:
            return None

        dataset["base_url"] = config.base_url
        dataset_uri = dataset["uri"]

        return formatter.format_dataset_details_record(
            dataset=dataset,
            authors=self.db.authors(item_uri=dataset_uri, item_type="dataset"),
            files=self.db.dataset_files(dataset_uri=dataset_uri),
            custom_fields=self.db.custom_fields(item_uri=dataset_uri, item_type="dataset"),
            tags=self.db.tags(item_uri=dataset_uri),
            categories=self.db.categories(item_uri=dataset_uri, limit=None),
            funding=self.db.fundings(item_uri=dataset_uri, item_type="dataset"),
            references=self.db.references(item_uri=dataset_uri),
        )

    def get_article_version_embargo(self, dataset_id, version) -> dict | None:
        """Return embargo record for a versioned article, or None if missing."""
        dataset = self._resolve_dataset(dataset_id, is_published=True, version=version)
        if dataset is None:
            return None
        return formatter.format_dataset_embargo_record(dataset)

    def get_article_version_confidentiality(self, dataset_id, version) -> dict | None:
        """Return confidentiality record for a versioned article."""
        dataset = self._resolve_dataset(dataset_id, is_published=True, version=version)
        if dataset is None:
            return None
        return formatter.format_dataset_confidentiality_record(dataset)

    def update_dataset_thumbnail(self, dataset_id, version, file_id, account_uuid) -> str | None:
        """Regenerate the dataset thumbnail from a file.

        Returns the new thumbnail extension on success, or ``None`` on any
        failure (dataset/file not found, no filesystem path, thumbnail
        generation failed, DB update failed). The legacy handler returns
        205 on success and 404/500 otherwise — callers map ``None`` to the
        appropriate HTTP status.
        """
        from djehuty.services.imaging import generate_thumbnail
        from djehuty.services.storage import filesystem_location

        dataset = self._resolve_dataset(dataset_id, version=version)
        if dataset is None:
            return None

        try:
            records = self.db.dataset_files(
                file_uuid=file_id,
                dataset_uri=dataset["uri"],
                account_uuid=account_uuid,
                limit=1,
            )
            metadata = records[0]
        except (IndexError, AttributeError, TypeError):
            return None

        input_path = filesystem_location(metadata)
        if input_path is None:
            return None

        extension = generate_thumbnail(input_path, dataset["uuid"])
        if extension is None:
            return None

        if not self.db.dataset_update_thumb(
            dataset_id, account_uuid, metadata["uuid"], extension, version
        ):
            return None

        return extension

    def get_article_file_details(self, dataset_id, file_id) -> dict | None:
        """Return details for a single file of a published article."""
        # AS-IS (#111): legacy dereferences dataset["uri"] with no None guard,
        # so a missing dataset (None) raises TypeError -> uncaught -> HTTP 500
        # (not 404). Reproduce: no None guard and no TypeError swallowing.
        dataset = self._resolve_dataset(dataset_id, is_published=True)
        records = self.db.dataset_files(dataset_uri=dataset["uri"])
        for record in records:
            if record.get("uuid") == file_id or str(record.get("id")) == str(file_id):
                record["base_url"] = config.base_url
                return formatter.format_file_for_dataset_record(record)
        return None

    def _resolve_dataset(
        self, dataset_id, account_uuid=None, is_latest=False, is_published=True, version=None
    ):
        """Resolve a dataset by numeric ID or UUID, optionally pinned to a version."""
        try:
            params = {
                "account_uuid": account_uuid,
                "is_latest": is_latest,
                "is_published": is_published,
                "limit": 1,
            }
            if version is not None:
                params["version"] = version
                # When a version is requested, is_latest must be unset so the
                # version filter takes effect.
                params["is_latest"] = False
            try:
                numeric_id = int(dataset_id)
                return self.db.datasets(dataset_id=numeric_id, **params)[0]
            except (ValueError, TypeError):
                return self.db.datasets(container_uuid=str(dataset_id), **params)[0]
        except (IndexError, AttributeError):
            return None
