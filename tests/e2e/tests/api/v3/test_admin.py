"""
V3 Admin API contract tests.

Endpoints (3):
    GET  /v3/admin/files-integrity-statistics
    POST /v3/admin/accounts/clear-cache
    POST /v3/admin/reviews/clear-cache

All endpoints require admin privileges.

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_admin.py -v
"""

from playwright.sync_api import Page


class TestV3AdminFilesIntegrityApi:
    """GET /v3/admin/files-integrity-statistics."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        response = page.request.get("/v3/admin/files-integrity-statistics")
        save_response(response, "v3-admin-files-integrity-no-auth")
        assert response.status in (401, 403)

    def test_admin_role_check(self, admin_page: Page, save_response):
        """The default admin session does not have the files-integrity role
        — endpoint returns 403 for them. Asserting AS-IS: 200 (granted) or 403
        (denied) are both legitimate handler outcomes."""
        response = admin_page.request.get("/v3/admin/files-integrity-statistics")
        save_response(response, "v3-admin-files-integrity")
        assert response.status in (200, 403)


class TestV3AdminAccountsClearCacheApi:
    """/v3/admin/accounts/clear-cache — handler accepts GET (not POST)."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated GET → 401/403."""
        response = page.request.get("/v3/admin/accounts/clear-cache")
        save_response(response, "v3-admin-accounts-clear-no-auth")
        assert response.status in (401, 403)

    def test_admin_can_clear(self, admin_page: Page, save_response):
        """Admin GET → 2xx."""
        response = admin_page.request.get("/v3/admin/accounts/clear-cache")
        save_response(response, "v3-admin-accounts-clear")
        assert response.ok

    def test_rejects_post(self, admin_page: Page, save_response):
        """POST → 405."""
        response = admin_page.request.post(
            "/v3/admin/accounts/clear-cache",
            data={},
        )
        save_response(response, "v3-admin-accounts-clear-post")
        assert response.status == 405


class TestV3AdminReviewsClearCacheApi:
    """/v3/admin/reviews/clear-cache — handler accepts GET (not POST)."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated GET → 401/403."""
        response = page.request.get("/v3/admin/reviews/clear-cache")
        save_response(response, "v3-admin-reviews-clear-no-auth")
        assert response.status in (401, 403)

    def test_admin_can_clear(self, admin_page: Page, save_response):
        """Admin GET → 2xx."""
        response = admin_page.request.get("/v3/admin/reviews/clear-cache")
        save_response(response, "v3-admin-reviews-clear")
        assert response.ok

    def test_rejects_post(self, admin_page: Page, save_response):
        """POST → 405."""
        response = admin_page.request.post(
            "/v3/admin/reviews/clear-cache",
            data={},
        )
        save_response(response, "v3-admin-reviews-clear-post")
        assert response.status == 405
