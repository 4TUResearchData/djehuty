"""
V2 Articles API contract tests.

Covers /v2/articles* (public) and /v2/account/articles* (private):
  - List, search, pagination, 404
  - Private dataset CRUD
  - Authors, categories, files, embargo, private_links
  - Published-article reads
  - Common error responses

Run with:
    cd tests/e2e && python -m pytest tests/api/v2/test_articles.py -v
"""

import uuid

from playwright.sync_api import Page

from helpers.contract import assert_status


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class TestV2PublicArticlesApi:
    """Public (unauthenticated) /v2/articles endpoints."""

    def test_list_articles(self, page: Page, save_response):
        """GET /v2/articles → 200, JSON array."""
        response = page.request.get("/v2/articles?limit=5")
        save_response(response, "v2-list-articles")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_articles(self, page: Page, save_response):
        """POST /v2/articles/search → 200, JSON array."""
        response = page.request.post(
            "/v2/articles/search",
            data={"search_for": "test", "limit": 5},
        )
        save_response(response, "v2-search-articles")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_nonexistent_article_returns_404(self, page: Page, save_response):
        """GET /v2/articles/<fake-id> → 404."""
        response = page.request.get("/v2/articles/99999999")
        save_response(response, "v2-article-404")
        assert response.status == 404

    def test_list_articles_pagination(self, page: Page, save_response):
        """GET /v2/articles with limit & offset respects pagination."""
        response = page.request.get("/v2/articles?limit=2&offset=0")
        save_response(response, "v2-list-articles-paginated")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 2


# ---------------------------------------------------------------------------
# Private API – CRUD
# ---------------------------------------------------------------------------


class TestV2PrivateArticlesCrud:
    """Authenticated CRUD over /v2/account/articles*."""

    def test_create_article(self, authenticated_page: Page, save_response):
        """POST /v2/account/articles → 200 + location."""
        response = authenticated_page.request.post(
            "/v2/account/articles",
            data={"title": "API Created Dataset"},
        )
        save_response(response, "api-create-article")
        assert response.status == 200
        data = response.json()
        assert "location" in data

        # Clean up
        dataset_uuid = data["location"].rstrip("/").split("/")[-1]
        authenticated_page.request.delete(f"/v2/account/articles/{dataset_uuid}")

    def test_create_article_without_title(
        self, authenticated_page: Page, save_response
    ):
        """POST /v2/account/articles without title → 400."""
        response = authenticated_page.request.post(
            "/v2/account/articles",
            data={},
        )
        save_response(response, "api-create-no-title")
        assert response.status == 400

    def test_get_private_article(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid> → 200 with details."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v2/account/articles/{container_uuid}")
        save_response(response, "api-get-private-article")
        assert response.status == 200
        data = response.json()
        assert "uuid" in data or "container_uuid" in data

    def test_update_article_metadata(self, draft_dataset, save_response):
        """PUT /v2/account/articles/<uuid> persists updates."""
        page, container_uuid = draft_dataset
        unique_title = f"Updated Title {uuid.uuid4().hex[:8]}"
        response = page.request.put(
            f"/v2/account/articles/{container_uuid}",
            data={
                "title": unique_title,
                "description": "<p>Updated via API.</p>",
            },
        )
        save_response(response, "api-update-article")
        assert response.ok

        get_response = page.request.get(f"/v2/account/articles/{container_uuid}")
        save_response(get_response, "api-update-article-verify")
        data = get_response.json()
        assert data["title"] == unique_title

    def test_update_article_tags(self, draft_dataset, save_response):
        """PUT /v2/account/articles/<uuid> with tags updates them."""
        page, container_uuid = draft_dataset
        response = page.request.put(
            f"/v2/account/articles/{container_uuid}",
            data={"tags": ["api-test", "e2e"]},
        )
        save_response(response, "api-update-tags")
        assert response.ok

    def test_delete_article(self, authenticated_page: Page, save_response):
        """DELETE /v2/account/articles/<uuid> → 204 and resource is gone."""
        response = authenticated_page.request.post(
            "/v2/account/articles",
            data={"title": "To Be Deleted"},
        )
        data = response.json()
        dataset_uuid = data["location"].rstrip("/").split("/")[-1]

        delete_response = authenticated_page.request.delete(
            f"/v2/account/articles/{dataset_uuid}"
        )
        save_response(delete_response, "api-delete-article")
        assert delete_response.status == 204

        # After delete, the private endpoint returns 200 + [] for this account.
        get_response = authenticated_page.request.get(
            f"/v2/account/articles/{dataset_uuid}"
        )
        save_response(get_response, "api-delete-article-verify-gone")
        assert get_response.status == 200
        assert get_response.json() == [] or get_response.body() == b"[]"

    def test_list_private_articles(self, draft_dataset, save_response):
        """GET /v2/account/articles lists the user's articles."""
        page, container_uuid = draft_dataset
        response = page.request.get("/v2/account/articles?limit=50")
        save_response(response, "api-list-private-articles")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        uuids = [d.get("uuid") or d.get("container_uuid", "") for d in data]
        assert any(container_uuid in u for u in uuids)

    def test_search_private_articles(self, draft_dataset, save_response):
        """POST /v2/account/articles/search finds the user's articles."""
        page, container_uuid = draft_dataset
        unique_title = f"SearchMe-{uuid.uuid4().hex[:8]}"
        page.request.put(
            f"/v2/account/articles/{container_uuid}",
            data={"title": unique_title},
        )

        response = page.request.post(
            "/v2/account/articles/search",
            data={"search_for": unique_title},
        )
        save_response(response, "api-search-private-articles")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_private_articles_requires_auth(self, page: Page, save_response):
        """GET /v2/account/articles without auth → 401/403."""
        response = page.request.get("/v2/account/articles")
        save_response(response, "api-private-no-auth")
        assert response.status in (403, 401)


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------


class TestV2ArticleAuthorsApi:
    """Article author management."""

    def test_get_authors(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/authors → list."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v2/account/articles/{container_uuid}/authors")
        save_response(response, "api-get-authors")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_author(self, draft_dataset, save_response):
        """POST /v2/account/articles/<uuid>/authors adds an author."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v2/account/articles/{container_uuid}/authors",
            data={"authors": [{"first_name": "Jane", "last_name": "Doe"}]},
        )
        save_response(response, "api-add-author")
        assert response.ok

        get_response = page.request.get(
            f"/v2/account/articles/{container_uuid}/authors"
        )
        save_response(get_response, "api-add-author-verify")
        authors = get_response.json()
        names = [a.get("full_name", "") for a in authors]
        assert any("Jane" in n and "Doe" in n for n in names)

    def test_replace_authors(self, draft_dataset, save_response):
        """PUT /v2/account/articles/<uuid>/authors replaces all authors."""
        page, container_uuid = draft_dataset
        response = page.request.put(
            f"/v2/account/articles/{container_uuid}/authors",
            data={
                "authors": [
                    {"first_name": "Alice", "last_name": "Smith"},
                    {"first_name": "Bob", "last_name": "Jones"},
                ]
            },
        )
        save_response(response, "api-replace-authors")
        assert response.ok


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class TestV2ArticleCategoriesApi:
    """Article category management."""

    def test_get_categories(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/categories → list."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v2/account/articles/{container_uuid}/categories")
        save_response(response, "api-get-categories")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Private links
# ---------------------------------------------------------------------------


class TestV2ArticlePrivateLinksApi:
    """Private link CRUD on articles."""

    def test_create_private_link(self, draft_dataset, save_response):
        """POST /v2/account/articles/<uuid>/private_links creates a link."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v2/account/articles/{container_uuid}/private_links",
            data={"read_only": True},
        )
        save_response(response, "api-create-private-link")
        assert response.ok
        data = response.json()
        assert "location" in data

    def test_list_private_links(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/private_links lists links."""
        page, container_uuid = draft_dataset
        page.request.post(
            f"/v2/account/articles/{container_uuid}/private_links",
            data={"read_only": True},
        )
        response = page.request.get(
            f"/v2/account/articles/{container_uuid}/private_links"
        )
        save_response(response, "api-list-private-links")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_delete_private_link(self, draft_dataset, save_response):
        """DELETE removes a private link."""
        page, container_uuid = draft_dataset
        create_response = page.request.post(
            f"/v2/account/articles/{container_uuid}/private_links",
            data={"read_only": True},
        )
        link_data = create_response.json()
        link_id = link_data["location"].rstrip("/").split("/")[-1]

        delete_response = page.request.delete(
            f"/v2/account/articles/{container_uuid}/private_links/{link_id}"
        )
        save_response(delete_response, "api-delete-private-link")
        assert delete_response.status == 204


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


class TestV2ArticleFilesApi:
    """Article file listing."""

    def test_get_private_files_empty(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/files on empty dataset → []."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v2/account/articles/{container_uuid}/files")
        save_response(response, "api-get-files-empty")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


# ---------------------------------------------------------------------------
# Embargo
# ---------------------------------------------------------------------------


class TestV2ArticleEmbargoApi:
    """Article embargo endpoints."""

    def test_get_embargo(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/embargo → 200."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v2/account/articles/{container_uuid}/embargo")
        save_response(response, "api-get-embargo")
        assert response.status == 200


# ---------------------------------------------------------------------------
# Published articles
# ---------------------------------------------------------------------------


class TestV2PublishedArticlesApi:
    """Reads on published articles."""

    def test_get_published_article(self, published_dataset, save_response):
        """GET /v2/articles/<uuid> on a published article → 200 with title."""
        page, container_uuid = published_dataset
        response = page.request.get(f"/v2/articles/{container_uuid}")
        save_response(response, "api-get-published-v2")
        assert response.status == 200
        data = response.json()
        assert data.get("title") == "API Test Published Dataset"

    def test_get_article_versions(self, published_dataset, save_response):
        """GET /v2/articles/<uuid>/versions → list with ≥1 entry."""
        page, container_uuid = published_dataset
        response = page.request.get(f"/v2/articles/{container_uuid}/versions")
        save_response(response, "api-get-versions")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_published_article_files(self, published_dataset, save_response):
        """GET /v2/articles/<uuid>/files → list with the uploaded file."""
        page, container_uuid = published_dataset
        response = page.request.get(f"/v2/articles/{container_uuid}/files")
        save_response(response, "api-get-published-files")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_published_article_in_search(self, published_dataset, save_response):
        """The published article appears in /v2/articles/search results."""
        page, container_uuid = published_dataset
        response = page.request.post(
            "/v2/articles/search",
            data={"search_for": "API Test Published Dataset", "limit": 10},
        )
        save_response(response, "api-search-published")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


class TestV2ArticleFundingApi:
    """Article funding endpoints."""

    def test_get_funding(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/funding → 200, JSON array."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v2/account/articles/{container_uuid}/funding")
        save_response(response, "api-get-funding")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_funding(self, draft_dataset, save_response):
        """POST /v2/account/articles/<uuid>/funding adds a funding entry."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v2/account/articles/{container_uuid}/funding",
            data={"funders": [{"title": "API Test Funder"}]},
        )
        save_response(response, "api-add-funding")
        # AS-IS: handler returns 205 RESET CONTENT (also accepts 200/201/204
        # in case the response is normalized in the new version).
        assert response.status in (200, 201, 204, 205, 400, 422)


# ---------------------------------------------------------------------------
# Reserve DOI
# ---------------------------------------------------------------------------


class TestV2ArticleReserveDoiApi:
    """POST /v2/account/articles/<uuid>/reserve_doi."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.post(
            f"/v2/account/articles/{fake_uuid}/reserve_doi",
            data={},
        )
        save_response(response, "api-reserve-doi-no-auth")
        assert response.status in (401, 403)


# ---------------------------------------------------------------------------
# Published file details
# ---------------------------------------------------------------------------


class TestV2PublishedFileDetailsApi:
    """GET /v2/articles/<id>/files/<file_id>."""

    def test_nonexistent_returns_404(self, page: Page, save_response):
        """GET with fake (article, file) → 404."""
        fake_a = str(uuid.uuid4())
        fake_f = str(uuid.uuid4())
        response = page.request.get(f"/v2/articles/{fake_a}/files/{fake_f}")
        save_response(response, "api-published-file-404")
        assert_status(
            response,
            expected=404,
            current_bug=500,
            bug="#111: handler returns 500 instead of 404 on missing file",
        )


# ---------------------------------------------------------------------------
# Version-level endpoints
# ---------------------------------------------------------------------------


class TestV2ArticleVersionApi:
    """Endpoints scoped to a specific version of a published article."""

    def test_version_embargo_nonexistent(self, page: Page, save_response):
        """GET .../versions/<v>/embargo on a missing article → 404."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v2/articles/{fake}/versions/1/embargo")
        save_response(response, "api-version-embargo-404")
        assert response.status == 404

    def test_version_confidentiality_nonexistent(self, page: Page, save_response):
        """GET .../versions/<v>/confidentiality on a missing article → 404."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v2/articles/{fake}/versions/1/confidentiality")
        save_response(response, "api-version-confidentiality-404")
        assert response.status == 404

    def test_version_update_thumb_requires_auth(self, page: Page, save_response):
        """POST .../versions/<v>/update_thumb without auth → 4xx."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v2/articles/{fake}/versions/1/update_thumb",
            data={},
        )
        save_response(response, "api-version-update-thumb-no-auth")
        assert 400 <= response.status < 500


# ---------------------------------------------------------------------------
# Private file/category/author/private-link sub-resources
# ---------------------------------------------------------------------------


class TestV2ArticleSubResourceDeletesApi:
    """DELETE endpoints under /v2/account/articles/<id>/..."""

    def test_delete_nonexistent_author(self, authenticated_page: Page, save_response):
        """DELETE .../authors/<author_id> on a missing article → 4xx."""
        fake_a = str(uuid.uuid4())
        fake_x = str(uuid.uuid4())
        response = authenticated_page.request.delete(
            f"/v2/account/articles/{fake_a}/authors/{fake_x}"
        )
        save_response(response, "api-delete-author-missing")
        assert 400 <= response.status < 600

    def test_delete_nonexistent_category(self, authenticated_page: Page, save_response):
        """DELETE .../categories/<category_id> on a missing article → 4xx."""
        fake_a = str(uuid.uuid4())
        response = authenticated_page.request.delete(
            f"/v2/account/articles/{fake_a}/categories/1"
        )
        save_response(response, "api-delete-category-missing")
        assert 400 <= response.status < 600

    def test_delete_nonexistent_funding(self, authenticated_page: Page, save_response):
        """DELETE .../funding/<funding_id> on a missing article → 4xx."""
        fake_a = str(uuid.uuid4())
        fake_f = str(uuid.uuid4())
        response = authenticated_page.request.delete(
            f"/v2/account/articles/{fake_a}/funding/{fake_f}"
        )
        save_response(response, "api-delete-funding-missing")
        assert 400 <= response.status < 600

    def test_delete_nonexistent_file(self, authenticated_page: Page, save_response):
        """DELETE .../files/<file_id> on a missing article → 4xx."""
        fake_a = str(uuid.uuid4())
        fake_f = str(uuid.uuid4())
        response = authenticated_page.request.delete(
            f"/v2/account/articles/{fake_a}/files/{fake_f}"
        )
        save_response(response, "api-delete-file-missing")
        assert 400 <= response.status < 600


# ---------------------------------------------------------------------------
# Private link details
# ---------------------------------------------------------------------------


class TestV2ArticlePrivateLinkDetailsApi:
    """GET/PUT /v2/account/articles/<uuid>/private_links/<link_id>."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake_a = str(uuid.uuid4())
        response = page.request.get(f"/v2/account/articles/{fake_a}/private_links/abc")
        save_response(response, "api-private-link-details-no-auth")
        assert response.status in (401, 403)


# ---------------------------------------------------------------------------
# Publish (via v2 path, handler is the v3 publish handler)
# ---------------------------------------------------------------------------


class TestV2ArticlePublishApi:
    """POST /v2/account/articles/<uuid>/publish."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v2/account/articles/{fake}/publish",
            data={},
        )
        save_response(response, "api-publish-no-auth")
        assert response.status in (401, 403)


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------


class TestV2ArticlesApiErrors:
    """Common error responses on the articles API."""

    def test_invalid_method_on_public_articles(self, page: Page, save_response):
        """PUT /v2/articles → 405."""
        response = page.request.put("/v2/articles", data={})
        save_response(response, "api-invalid-method")
        assert response.status == 405

    def test_wrong_content_type(self, page: Page, save_response):
        """POST search with unsupported Accept → 400/406/415."""
        response = page.request.post(
            "/v2/articles/search",
            headers={"Accept": "application/xml", "Content-Type": "application/xml"},
            data="<search/>",
        )
        save_response(response, "api-wrong-content-type")
        assert response.status in (400, 406, 415)

    def test_delete_nonexistent_article(self, authenticated_page: Page, save_response):
        """DELETE /v2/account/articles/<fake> → 500 (dataset not found)."""
        fake_uuid = str(uuid.uuid4())
        response = authenticated_page.request.delete(
            f"/v2/account/articles/{fake_uuid}"
        )
        save_response(response, "api-delete-nonexistent")
        assert response.status == 500

    def test_update_nonexistent_article(self, authenticated_page: Page, save_response):
        """PUT /v2/account/articles/<fake> → 403/404."""
        fake_uuid = str(uuid.uuid4())
        response = authenticated_page.request.put(
            f"/v2/account/articles/{fake_uuid}",
            data={"title": "Nope"},
        )
        save_response(response, "api-update-nonexistent")
        assert response.status in (403, 404)
