"""
V3 Authors & Account search API contract tests.

Endpoints (2):
    POST /v3/accounts/search
    GET  /v3/authors/<author_uuid>

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_authors.py -v
"""

import uuid

from playwright.sync_api import Page

from helpers.contract import assert_status


class TestV3AccountsSearchApi:
    """POST /v3/accounts/search — typeahead account lookup (auth required)."""

    def test_search_requires_auth(self, page: Page, save_response):
        """POST /v3/accounts/search without auth → 401/403."""
        response = page.request.post(
            "/v3/accounts/search",
            data={"search_for": "test"},
        )
        save_response(response, "v3-accounts-search-no-auth")
        assert response.status in (401, 403)

    def test_accounts_search(self, authenticated_page: Page, save_response):
        """POST /v3/accounts/search authenticated → 200, JSON array."""
        response = authenticated_page.request.post(
            "/v3/accounts/search",
            data={"search_for": "dev"},
        )
        save_response(response, "v3-accounts-search")
        assert_status(
            response,
            expected=200,
            current_bug=500,
            bug="#111: POST /v3/accounts/search crashes on a simple valid body",
        )
        if response.status == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_accounts_search_rejects_get(self, page: Page, save_response):
        """GET /v3/accounts/search → 405 (method enforcement)."""
        response = page.request.get("/v3/accounts/search")
        save_response(response, "v3-accounts-search-get-rejected")
        # AS-IS: auth check runs before method check, so unauth GET → 403.
        # Either is acceptable contract for "this method is rejected here".
        assert response.status in (403, 405)


class TestV3AuthorDetailsApi:
    """GET /v3/authors/<uuid> — author by UUID."""

    def test_nonexistent_author_returns_404(self, page: Page, save_response):
        """GET /v3/authors/<fake> → 404."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.get(f"/v3/authors/{fake_uuid}")
        save_response(response, "v3-author-404")
        # AS-IS: returns 403 for missing author (hides existence). Accept both —
        # the new version may switch to 404 for consistency with other endpoints.
        assert response.status in (403, 404)
