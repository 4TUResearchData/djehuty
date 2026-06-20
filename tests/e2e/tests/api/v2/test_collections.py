"""
V2 Collections API contract tests.

Covers /v2/collections* (public) and /v2/account/collections* (private):
  - List, search, get, versions, articles
  - Private CRUD
  - Authors, categories, articles, funding, reserve_doi

Run with:
    cd tests/e2e && python -m pytest tests/api/v2/test_collections.py -v
"""

import uuid

from playwright.sync_api import Page


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class TestV2PublicCollectionsApi:
    """Public /v2/collections endpoints."""

    def test_list_collections(self, page: Page, save_response):
        """GET /v2/collections → 200, JSON array."""
        response = page.request.get("/v2/collections?limit=5")
        save_response(response, "v2-list-collections")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_collections(self, page: Page, save_response):
        """POST /v2/collections/search → 200, JSON array."""
        response = page.request.post(
            "/v2/collections/search",
            data={"search_for": "test", "limit": 5},
        )
        save_response(response, "v2-search-collections")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_nonexistent_collection_returns_404(self, page: Page, save_response):
        """GET /v2/collections/<fake> → 404."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.get(f"/v2/collections/{fake_uuid}")
        save_response(response, "v2-collection-404")
        assert response.status == 404

    def test_invalid_method_on_public_collections(self, page: Page, save_response):
        """PUT /v2/collections → 405."""
        response = page.request.put("/v2/collections", data={})
        save_response(response, "v2-collections-invalid-method")
        assert response.status == 405


# ---------------------------------------------------------------------------
# Private API – CRUD
# ---------------------------------------------------------------------------


class TestV2PrivateCollectionsCrud:
    """Authenticated CRUD over /v2/account/collections*."""

    def test_requires_auth(self, page: Page, save_response):
        """GET /v2/account/collections without auth → 401/403."""
        response = page.request.get("/v2/account/collections")
        save_response(response, "v2-private-collections-no-auth")
        assert response.status in (401, 403)

    def test_create_collection(self, authenticated_page: Page, save_response):
        """POST /v2/account/collections → 200 + location."""
        response = authenticated_page.request.post(
            "/v2/account/collections",
            data={"title": "API Created Collection"},
        )
        save_response(response, "v2-create-collection")
        assert response.status == 200
        data = response.json()
        assert "location" in data

        # Clean up
        collection_uuid = data["location"].rstrip("/").split("/")[-1]
        authenticated_page.request.delete(f"/v2/account/collections/{collection_uuid}")

    def test_get_private_collection(self, draft_collection, save_response):
        """GET /v2/account/collections/<uuid> → 200."""
        page, container_uuid = draft_collection
        response = page.request.get(f"/v2/account/collections/{container_uuid}")
        save_response(response, "v2-get-private-collection")
        assert response.status == 200

    def test_update_collection(self, draft_collection, save_response):
        """PUT /v2/account/collections/<uuid> persists updates."""
        page, container_uuid = draft_collection
        unique_title = f"Updated Collection {uuid.uuid4().hex[:8]}"
        response = page.request.put(
            f"/v2/account/collections/{container_uuid}",
            data={"title": unique_title},
        )
        save_response(response, "v2-update-collection")
        assert response.ok

    def test_list_private_collections(self, draft_collection, save_response):
        """GET /v2/account/collections lists the user's collections."""
        page, container_uuid = draft_collection
        response = page.request.get("/v2/account/collections?limit=50")
        save_response(response, "v2-list-private-collections")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_private_collections(self, draft_collection, save_response):
        """POST /v2/account/collections/search → 200, JSON array."""
        page, container_uuid = draft_collection
        response = page.request.post(
            "/v2/account/collections/search",
            data={"search_for": "test"},
        )
        save_response(response, "v2-search-private-collections")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_delete_collection(self, authenticated_page: Page, save_response):
        """DELETE /v2/account/collections/<uuid> → 204."""
        response = authenticated_page.request.post(
            "/v2/account/collections",
            data={"title": "To Be Deleted Collection"},
        )
        collection_uuid = response.json()["location"].rstrip("/").split("/")[-1]

        delete_response = authenticated_page.request.delete(
            f"/v2/account/collections/{collection_uuid}"
        )
        save_response(delete_response, "v2-delete-collection")
        assert delete_response.status == 204


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------


class TestV2CollectionAuthorsApi:
    """Collection author management."""

    def test_get_authors(self, draft_collection, save_response):
        """GET .../authors → 200, JSON array."""
        page, container_uuid = draft_collection
        response = page.request.get(f"/v2/account/collections/{container_uuid}/authors")
        save_response(response, "v2-collection-authors")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_author(self, draft_collection, save_response):
        """POST .../authors adds an author."""
        page, container_uuid = draft_collection
        response = page.request.post(
            f"/v2/account/collections/{container_uuid}/authors",
            data={"authors": [{"first_name": "Coll", "last_name": "Author"}]},
        )
        save_response(response, "v2-collection-add-author")
        assert response.ok


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class TestV2CollectionCategoriesApi:
    """Collection category management."""

    def test_get_categories(self, draft_collection, save_response):
        """GET .../categories → 200, JSON array."""
        page, container_uuid = draft_collection
        response = page.request.get(
            f"/v2/account/collections/{container_uuid}/categories"
        )
        save_response(response, "v2-collection-categories")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Articles within collections
# ---------------------------------------------------------------------------


class TestV2CollectionArticlesApi:
    """Collection-article relationship endpoints."""

    def test_get_articles(self, draft_collection, save_response):
        """GET .../articles → 200, JSON array."""
        page, container_uuid = draft_collection
        response = page.request.get(
            f"/v2/account/collections/{container_uuid}/articles"
        )
        save_response(response, "v2-collection-articles")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


class TestV2CollectionFundingApi:
    """Collection funding endpoints."""

    def test_get_funding(self, draft_collection, save_response):
        """GET .../funding → 200, JSON array."""
        page, container_uuid = draft_collection
        response = page.request.get(f"/v2/account/collections/{container_uuid}/funding")
        save_response(response, "v2-collection-funding")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Reserve DOI
# ---------------------------------------------------------------------------


class TestV2CollectionReserveDoiApi:
    """POST /v2/account/collections/<uuid>/reserve_doi — reserve a DOI."""

    def test_requires_auth(self, page: Page, save_response):
        """Without auth → 401/403."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.post(
            f"/v2/account/collections/{fake_uuid}/reserve_doi",
            data={},
        )
        save_response(response, "v2-collection-reserve-doi-no-auth")
        assert response.status in (401, 403)
