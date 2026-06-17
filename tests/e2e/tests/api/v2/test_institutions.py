"""
V2 Institutions API contract tests.

Endpoints (3):
    GET   /v2/account/institution
    GET   /v2/account/institution/users/<account_id>
    GET   /v2/account/institution/accounts

Run with:
    cd tests/e2e && python -m pytest tests/api/v2/test_institutions.py -v
"""

import uuid

from playwright.sync_api import Page

from helpers.contract import assert_status


class TestV2InstitutionApi:
    """GET /v2/account/institution."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        response = page.request.get("/v2/account/institution")
        save_response(response, "v2-institution-no-auth")
        assert response.status in (401, 403)

    def test_get_institution(self, authenticated_page: Page, save_response):
        """Authenticated → 200 with {id, name}."""
        response = authenticated_page.request.get("/v2/account/institution")
        save_response(response, "v2-institution")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "id" in data
        assert "name" in data


class TestV2InstitutionAccountsApi:
    """GET /v2/account/institution/accounts — admin-only listing."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        response = page.request.get("/v2/account/institution/accounts")
        save_response(response, "v2-institution-accounts-no-auth")
        assert response.status in (401, 403)

    def test_admin_can_list_accounts(self, admin_page: Page, save_response):
        """Admin → 200, JSON array."""
        response = admin_page.request.get("/v2/account/institution/accounts?limit=5")
        save_response(response, "v2-institution-accounts")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


class TestV2InstitutionAccountApi:
    """GET /v2/account/institution/users/<id>."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.get(f"/v2/account/institution/users/{fake_uuid}")
        save_response(response, "v2-institution-user-no-auth")
        assert response.status in (401, 403)

    def test_invalid_id_returns_400(self, authenticated_page: Page, save_response):
        """An id that's neither integer nor UUID → 400."""
        response = authenticated_page.request.get(
            "/v2/account/institution/users/not-an-id"
        )
        save_response(response, "v2-institution-user-bad-id")
        assert_status(
            response,
            expected=400,
            current_bug=200,
            bug="#111: returns 200 with a blank record instead of 400 on invalid id",
        )
