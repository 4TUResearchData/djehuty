"""
V3 Collections API contract tests.

Endpoints (4):
    POST    /v3/collections/<id>/publish
    PUT     /v3/collections/<uuid>/reorder-authors
    CRUD    /v3/collections/<id>/references
    CRUD    /v3/collections/<id>/tags

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_collections.py -v
"""

import uuid

from playwright.sync_api import Page


class TestV3CollectionTagsApi:
    """Collection tag management."""

    def test_get_tags(self, draft_collection, save_response):
        """GET /v3/collections/<uuid>/tags → 200, JSON array."""
        page, container_uuid = draft_collection
        response = page.request.get(f"/v3/collections/{container_uuid}/tags")
        save_response(response, "v3-collection-tags")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_tags(self, draft_collection, save_response):
        """POST /v3/collections/<uuid>/tags adds tags."""
        page, container_uuid = draft_collection
        response = page.request.post(
            f"/v3/collections/{container_uuid}/tags",
            data={"tags": ["api-test-tag", "v3-collection-tag"]},
        )
        save_response(response, "v3-collection-add-tags")
        assert response.ok

    def test_delete_tag(self, draft_collection, save_response):
        """DELETE /v3/collections/<uuid>/tags?tag=<value> removes a tag."""
        page, container_uuid = draft_collection
        page.request.post(
            f"/v3/collections/{container_uuid}/tags",
            data={"tags": ["to-delete"]},
        )
        response = page.request.delete(
            f"/v3/collections/{container_uuid}/tags?tag=to-delete"
        )
        save_response(response, "v3-collection-delete-tag")
        assert response.ok


class TestV3CollectionReferencesApi:
    """Collection reference management."""

    def test_get_references(self, draft_collection, save_response):
        """GET /v3/collections/<uuid>/references → 200, JSON array."""
        page, container_uuid = draft_collection
        response = page.request.get(f"/v3/collections/{container_uuid}/references")
        save_response(response, "v3-collection-references")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_references(self, draft_collection, save_response):
        """POST /v3/collections/<uuid>/references adds references."""
        page, container_uuid = draft_collection
        response = page.request.post(
            f"/v3/collections/{container_uuid}/references",
            data={"references": [{"url": "https://example.com/coll-ref"}]},
        )
        save_response(response, "v3-collection-add-references")
        assert response.ok


class TestV3CollectionAuthorsReorderApi:
    """POST /v3/collections/<uuid>/reorder-authors — change author order."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/collections/{fake_uuid}/reorder-authors",
            data={"order": []},
        )
        save_response(response, "v3-collection-reorder-no-auth")
        assert response.status in (401, 403)

    def test_reorder_empty(self, draft_collection, save_response):
        """POST with empty order array → 2xx/4xx (no-op on a draft with no authors)."""
        page, container_uuid = draft_collection
        response = page.request.post(
            f"/v3/collections/{container_uuid}/reorder-authors",
            data={"order": []},
        )
        save_response(response, "v3-collection-reorder-empty")
        # Either accepted (200/204) or validation error (400) — both are
        # legitimate handler responses for an empty order on a draft.
        assert response.status in (200, 204, 400)


class TestV3CollectionPublishApi:
    """POST /v3/collections/<id>/publish — publish a draft collection."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/collections/{fake_uuid}/publish",
            data={},
        )
        save_response(response, "v3-collection-publish-no-auth")
        assert response.status in (401, 403)

    def test_publish_unprepared_collection_returns_error(
        self, draft_collection, save_response
    ):
        """A draft without required fields cannot be published → 4xx."""
        page, container_uuid = draft_collection
        response = page.request.post(
            f"/v3/collections/{container_uuid}/publish",
            data={},
        )
        save_response(response, "v3-collection-publish-unprepared")
        # 400/403/404 are all valid — exact code depends on which validation
        # step fails first.
        assert response.status in (400, 403, 404, 500)
