"""
V3 Profile API contract tests.

Endpoints (5):
    PUT   /v3/profile                        (auth)
    GET   /v3/profile/categories             (auth)
    POST  /v3/profile/quota-request          (auth)
    GET/POST /v3/profile/picture             (auth)
    GET   /v3/profile/picture/<account_uuid> (auth)

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_profile.py -v
"""

import uuid

from playwright.sync_api import Page

from helpers.contract import assert_status


class TestV3ProfileApi:
    """PUT /v3/profile — update the current account's profile."""

    def test_requires_auth(self, page: Page, save_response):
        """PUT without auth → 401/403."""
        response = page.request.put("/v3/profile", data={"first_name": "Anon"})
        save_response(response, "v3-profile-no-auth")
        assert response.status in (401, 403)

    def test_update_profile(self, authenticated_page: Page, save_response):
        """PUT /v3/profile with valid fields → 204."""
        response = authenticated_page.request.put(
            "/v3/profile",
            data={
                "first_name": "API",
                "last_name": "Tester",
                "location": "Delft",
            },
        )
        save_response(response, "v3-profile-update")
        assert response.status == 204


class TestV3ProfileCategoriesApi:
    """GET /v3/profile/categories — categories of the current account."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        response = page.request.get("/v3/profile/categories")
        save_response(response, "v3-profile-categories-no-auth")
        assert response.status in (401, 403)

    def test_list_categories(self, authenticated_page: Page, save_response):
        """Authenticated → 200, JSON array."""
        response = authenticated_page.request.get("/v3/profile/categories")
        save_response(response, "v3-profile-categories")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


class TestV3ProfileQuotaRequestApi:
    """POST /v3/profile/quota-request."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        response = page.request.post(
            "/v3/profile/quota-request",
            data={"new-quota": 100, "reason": "Need more space."},
        )
        save_response(response, "v3-quota-no-auth")
        assert response.status in (401, 403)

    def test_quota_too_small_returns_400(self, authenticated_page: Page, save_response):
        """new-quota < 1 GB → 400 QuotaRequestSizeTooSmall."""
        response = authenticated_page.request.post(
            "/v3/profile/quota-request",
            data={"new-quota": 0, "reason": "Test bad request."},
        )
        save_response(response, "v3-quota-too-small")
        assert response.status == 400


class TestV3ProfilePictureApi:
    """GET /v3/profile/picture — fetch own profile picture (or default)."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        response = page.request.get("/v3/profile/picture")
        save_response(response, "v3-profile-picture-no-auth")
        assert response.status in (401, 403)


class TestV3ProfilePictureForAccountApi:
    """GET /v3/profile/picture/<account_uuid> — fetch any account's picture."""

    def test_nonexistent_account(self, authenticated_page: Page, save_response):
        """GET picture for a fake UUID → 404 or default 200 image."""
        fake_uuid = str(uuid.uuid4())
        response = authenticated_page.request.get(f"/v3/profile/picture/{fake_uuid}")
        save_response(response, "v3-profile-picture-fake")
        # Either default fallback (200), not-found (404), or the AS-IS crash (500).
        assert_status(
            response,
            expected=404,
            current_bug=500,
            bug="#111: /v3/profile/picture/<uuid> returns 500 instead of 404 for missing account",
        )
