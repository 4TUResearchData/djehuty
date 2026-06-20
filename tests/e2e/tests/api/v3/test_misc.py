"""
V3 Miscellaneous API contract tests.

Endpoints (4):
    GET  /v3/codemeta
    GET  /v3/groups
    POST /v3/tags/search
    GET  /v3/file/<file_id>

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_misc.py -v
"""

import uuid

from playwright.sync_api import Page


class TestV3CodemetaApi:
    """GET /v3/codemeta — codemeta export for published software."""

    def test_list_codemeta(self, page: Page, save_response):
        """GET /v3/codemeta → 200, JSON array."""
        response = page.request.get("/v3/codemeta?limit=5")
        save_response(response, "v3-codemeta")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_codemeta_invalid_paging_400(self, page: Page, save_response):
        """GET /v3/codemeta with invalid limit → 400."""
        response = page.request.get("/v3/codemeta?limit=not-a-number")
        save_response(response, "v3-codemeta-bad-limit")
        assert response.status == 400


class TestV3GroupsApi:
    """GET /v3/groups — institutional groups list."""

    def test_list_groups(self, page: Page, save_response):
        """GET /v3/groups → 200, JSON array."""
        response = page.request.get("/v3/groups")
        save_response(response, "v3-groups")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


class TestV3TagsSearchApi:
    """POST /v3/tags/search — autocomplete-style tag search."""

    def test_tags_search(self, page: Page, save_response):
        """POST /v3/tags/search returns matching tags."""
        response = page.request.post(
            "/v3/tags/search",
            data={"search_for": "test"},
        )
        save_response(response, "v3-tags-search")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_tags_search_rejects_get(self, page: Page, save_response):
        """GET /v3/tags/search → 405."""
        response = page.request.get("/v3/tags/search")
        save_response(response, "v3-tags-search-get-rejected")
        assert response.status == 405


class TestV3FileApi:
    """GET /v3/file/<id> — file metadata by ID."""

    def test_file_nonexistent_returns_404(self, page: Page, save_response):
        """GET /v3/file/<fake-uuid> → 403/404."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.get(f"/v3/file/{fake_uuid}")
        save_response(response, "v3-file-404")
        assert response.status in (403, 404)
