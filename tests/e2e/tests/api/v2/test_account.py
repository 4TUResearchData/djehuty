"""
V2 Account / OAuth API contract tests.

Endpoints (4):
    GET/POST  /v2/account/applications/authorize
    POST      /v2/token
    GET       /v2/account
    POST      /v2/account/funding/search

Run with:
    cd tests/e2e && python -m pytest tests/api/v2/test_account.py -v
"""

from playwright.sync_api import Page


class TestV2AccountApi:
    """GET /v2/account — current account info."""

    def test_get_account_requires_auth(self, page: Page, save_response):
        """GET /v2/account without auth → 401/403."""
        response = page.request.get("/v2/account")
        save_response(response, "v2-account-no-auth")
        assert response.status in (401, 403)

    def test_get_account_authenticated(self, authenticated_page: Page, save_response):
        """GET /v2/account authenticated → 200 with account record."""
        response = authenticated_page.request.get("/v2/account")
        save_response(response, "v2-account")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, dict)
        # Account records expose at least an id/uuid and email.
        assert "id" in data or "uuid" in data


class TestV2FundingSearchApi:
    """POST /v2/account/funding/search."""

    def test_funding_search_requires_auth(self, page: Page, save_response):
        """POST /v2/account/funding/search without auth → 401/403."""
        response = page.request.post(
            "/v2/account/funding/search",
            data={"search": "test"},
        )
        save_response(response, "v2-funding-search-no-auth")
        assert response.status in (401, 403)

    def test_funding_search_authenticated(
        self, authenticated_page: Page, save_response
    ):
        """POST /v2/account/funding/search authenticated → 200, JSON array."""
        response = authenticated_page.request.post(
            "/v2/account/funding/search",
            data={"search": "research"},
        )
        save_response(response, "v2-funding-search")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


class TestV2OAuthApi:
    """OAuth endpoints: /v2/token and /v2/account/applications/authorize.

    Djehuty's OAuth surface is minimal — these handlers exist for compatibility
    with consumers that expect a Figshare-style OAuth flow but the dev
    deployment uses session-based auth. We only assert the routes are reachable
    and reject malformed requests, not the full OAuth dance.
    """

    def test_token_endpoint_rejects_get(self, page: Page, save_response):
        """GET /v2/token → 4xx (token endpoint is POST)."""
        response = page.request.get("/v2/token")
        save_response(response, "v2-token-get")
        assert 400 <= response.status < 500

    def test_token_endpoint_rejects_empty_post(self, page: Page, save_response):
        """POST /v2/token with no body → 4xx."""
        response = page.request.post("/v2/token", data={})
        save_response(response, "v2-token-empty-post")
        assert 400 <= response.status < 500

    def test_authorize_endpoint_rejects_unsigned(self, page: Page, save_response):
        """GET /v2/account/applications/authorize without client_id → 4xx."""
        response = page.request.get("/v2/account/applications/authorize")
        save_response(response, "v2-authorize-unsigned")
        assert 400 <= response.status < 500
