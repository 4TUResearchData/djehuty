"""
V2 Authors API contract tests.

Endpoints (2):
    POST  /v2/account/authors/search
    GET   /v2/account/authors/<author_id>

Run with:
    cd tests/e2e && python -m pytest tests/api/v2/test_authors.py -v
"""

import uuid

from playwright.sync_api import Page


class TestV2PrivateAuthorsSearchApi:
    """POST /v2/account/authors/search — admin-only typeahead."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        response = page.request.post(
            "/v2/account/authors/search",
            data={"search": "test"},
        )
        save_response(response, "v2-private-authors-search-no-auth")
        assert response.status in (401, 403)

    def test_admin_can_search(self, admin_page: Page, save_response):
        """Admin → 200, JSON array."""
        response = admin_page.request.post(
            "/v2/account/authors/search",
            data={"search": "test"},
        )
        save_response(response, "v2-private-authors-search")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


class TestV2PrivateAuthorDetailsApi:
    """GET /v2/account/authors/<id> — admin-only details."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.get(f"/v2/account/authors/{fake_uuid}")
        save_response(response, "v2-private-author-no-auth")
        assert response.status in (401, 403)

    def test_invalid_id_returns_404(self, admin_page: Page, save_response):
        """Admin with an id that isn't an integer or UUID → 404."""
        response = admin_page.request.get("/v2/account/authors/not-an-id")
        save_response(response, "v2-private-author-bad-id")
        assert response.status == 404

    def test_nonexistent_author_returns_403_or_404(
        self, admin_page: Page, save_response
    ):
        """Admin with a syntactically-valid id for a missing author → 403/404."""
        fake_uuid = str(uuid.uuid4())
        response = admin_page.request.get(f"/v2/account/authors/{fake_uuid}")
        save_response(response, "v2-private-author-missing")
        assert response.status in (403, 404)
