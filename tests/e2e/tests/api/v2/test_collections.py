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

from helpers.contract import assert_status
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
        uuids = [d.get("uuid") or d.get("container_uuid", "") for d in data]
        assert any(container_uuid in u for u in uuids)

    def test_search_private_collections(self, draft_collection, save_response):
        """POST /v2/account/collections/search finds the user's collections."""
        page, container_uuid = draft_collection
        unique_title = f"SearchMe-{uuid.uuid4().hex[:8]}"
        page.request.put(
            f"/v2/account/collections/{container_uuid}",
            data={"title": unique_title},
        )

        response = page.request.post(
            "/v2/account/collections/search",
            data={"search_for": unique_title},
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

    def test_delete_nonexistent_collection(self, authenticated_page: Page, save_response):
        """DELETE /v2/account/collections/<fake> → 404.

        Unlike the articles path (which returns 500 AS-IS, #111), the
        collections handler already 404s on a missing collection; this locks
        that behaviour.
        """
        fake_uuid = str(uuid.uuid4())
        response = authenticated_page.request.delete(f"/v2/account/collections/{fake_uuid}")
        save_response(response, "v2-delete-nonexistent-collection")
        assert response.status == 404


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

    def test_replace_authors(self, draft_collection, save_response):
        """PUT replaces collection authors; an empty list clears them."""
        page, container_uuid = draft_collection
        authors_url = f"/v2/account/collections/{container_uuid}/authors"
        create_response = page.request.post(
            authors_url,
            data={"authors": [{"first_name": "Original", "last_name": "Author"}]},
        )
        assert create_response.status == 205
        before_response = page.request.get(authors_url)
        assert before_response.status == 200
        assert any(author["full_name"] == "Original Author" for author in before_response.json())

        response = page.request.put(
            authors_url,
            data={"authors": [{"first_name": "Replacement", "last_name": "Author"}]},
        )
        save_response(response, "v2-collection-replace-authors")
        assert response.status == 205

        get_response = page.request.get(authors_url)
        save_response(get_response, "v2-collection-replace-authors-verify")
        assert get_response.status == 200
        assert [author["full_name"] for author in get_response.json()] == ["Replacement Author"]

        clear_response = page.request.put(authors_url, data={"authors": []})
        assert clear_response.status == 205
        get_response = page.request.get(authors_url)
        save_response(get_response, "v2-collection-clear-authors-verify")
        assert get_response.status == 200
        assert get_response.json() == []

    def test_add_email_and_orcid_matching_same_author_does_not_duplicate(
        self, draft_dataset, draft_collection, save_response
    ):
        """POST adds one collection author when email and ORCID match one account."""
        from config import AUTO_LOGIN_EMAIL

        page, dataset_uuid = draft_dataset
        _, collection_uuid = draft_collection
        authors_url = f"/v2/account/collections/{collection_uuid}/authors"

        source_response = page.request.get(f"/v2/account/articles/{dataset_uuid}/authors")
        assert source_response.status == 200
        source_authors = source_response.json()
        assert len(source_authors) == 1
        matching_author = source_authors[0]
        assert matching_author.get("is_active") is True
        matching_uuid = matching_author["uuid"]
        matching_orcid = matching_author["orcid_id"]
        assert matching_orcid

        before_response = page.request.get(authors_url)
        assert before_response.status == 200
        before_uuids = [author["uuid"] for author in before_response.json()]
        if matching_uuid in before_uuids:
            remove_response = page.request.delete(f"{authors_url}/{matching_uuid}")
            assert remove_response.status == 204

        before_response = page.request.get(authors_url)
        assert before_response.status == 200
        before_uuids = [author["uuid"] for author in before_response.json()]
        assert matching_uuid not in before_uuids

        response = page.request.post(
            authors_url,
            data={
                "authors": [
                    {"first_name": "Dev", "last_name": "User", "email": AUTO_LOGIN_EMAIL},
                    {"first_name": "Dev", "last_name": "User", "orcid_id": matching_orcid},
                ]
            },
        )
        save_response(response, "api-add-collection-author-by-email-and-orcid")
        assert response.status == 205

        get_response = page.request.get(authors_url)
        save_response(get_response, "api-add-collection-author-by-email-and-orcid-verify")
        assert get_response.status == 200
        authors = get_response.json()
        assert [author["uuid"] for author in authors] == before_uuids + [matching_uuid]
        assert authors[-1].get("is_active") is True


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class TestV2CollectionCategoriesApi:
    """Collection category management."""

    def test_get_categories(self, draft_collection, save_response):
        """GET .../categories → 200, JSON array."""
        page, container_uuid = draft_collection
        response = page.request.get(f"/v2/account/collections/{container_uuid}/categories")
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
        response = page.request.get(f"/v2/account/collections/{container_uuid}/articles")
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


# ---------------------------------------------------------------------------
# Category ops against a PUBLISHED collection (private resolver rejects it)
# ---------------------------------------------------------------------------


class TestV2PublishedCollectionCategoriesStatus:
    """The private resolver rejects a published id; legacy then crashes (GET)
    or refuses (DELETE). Pinned so a new/legacy flip stays invisible."""

    def test_get_categories_on_published_is_500(self, published_collection, save_response):
        page, container_uuid = published_collection
        response = page.request.get(f"/v2/account/collections/{container_uuid}/categories")
        save_response(response, "api-get-published-collection-categories")
        assert_status(
            response,
            expected=404,
            current_bug=500,
            bug="dereferences a published collection -> 500",
        )

    def test_delete_category_on_published_is_403(self, published_collection, save_response):
        page, container_uuid = published_collection
        response = page.request.delete(f"/v2/account/collections/{container_uuid}/categories/1")
        save_response(response, "api-delete-published-collection-category")
        assert_status(response, expected=403)
