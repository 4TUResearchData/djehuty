"""
Authentication and authorization tests.

Covers:
    - Logout (session cleared, redirected to /)
    - Protected pages return 403 when unauthenticated
    - Admin impersonation: switch user and stop impersonation

Run with:
    cd e2e && python -m pytest tests/test_auth.py -v
"""

import pytest
from playwright.sync_api import Page, expect

from config import BASE_URL
from helpers.accounts import get_non_admin_account_uuid


@pytest.mark.auth
class TestLogout:
    """Verify that logging out clears the session."""

    def test_logout_redirects_to_home(self, authenticated_page: Page, screenshot):
        """After logout the user should be redirected to /."""
        screenshot(authenticated_page, "logged-in")
        authenticated_page.goto("/logout")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "after-logout")
        expect(authenticated_page).to_have_url(f"{BASE_URL}/")

    def test_logout_clears_session(self, authenticated_page: Page, screenshot):
        """After logout, accessing a protected page should fail (403)."""
        authenticated_page.goto("/logout")
        authenticated_page.wait_for_load_state("domcontentloaded")

        response = authenticated_page.goto("/my/dashboard")
        assert response is not None
        screenshot(authenticated_page, "protected-page-after-logout")
        assert response.status == 403

    def test_logout_button_visible(self, authenticated_page: Page, screenshot):
        """The logout button should be visible when logged in."""
        authenticated_page.goto("/my/dashboard")
        screenshot(authenticated_page, "dashboard-with-logout-button")
        logout_button = authenticated_page.locator("#logout-button")
        expect(logout_button).to_be_visible()

    def test_logout_button_not_visible_when_logged_out(self, page: Page, screenshot):
        """The logout button should not be present on public pages."""
        page.goto("/portal")
        screenshot(page, "portal-no-logout-button")
        logout_button = page.locator("#logout-button")
        expect(logout_button).not_to_be_visible()


@pytest.mark.auth
class TestProtectedPages:
    """Verify that protected pages deny access to unauthenticated users."""

    def test_my_dashboard_requires_auth(self, page: Page, screenshot):
        """GET /my/dashboard without a session should return 403."""
        response = page.goto("/my/dashboard")
        assert response is not None
        screenshot(page, "my-dashboard-403")
        assert response.status == 403

    def test_admin_dashboard_requires_auth(self, page: Page, screenshot):
        """GET /admin/dashboard without a session should return 403."""
        response = page.goto("/admin/dashboard")
        assert response is not None
        screenshot(page, "admin-dashboard-403")
        assert response.status == 403

    def test_my_datasets_requires_auth(self, page: Page, screenshot):
        """GET /my/datasets without a session should return 403."""
        response = page.goto("/my/datasets")
        assert response is not None
        screenshot(page, "my-datasets-403")
        assert response.status == 403

    def test_admin_users_requires_auth(self, page: Page, screenshot):
        """GET /admin/users without a session should return 403."""
        response = page.goto("/admin/users")
        assert response is not None
        screenshot(page, "admin-users-403")
        assert response.status == 403


@pytest.mark.auth
class TestImpersonation:
    """Test admin impersonation to switch between users."""

    def test_impersonate_switches_user(self, admin_page: Page, screenshot):
        """Impersonating a user should show the impersonation banner."""
        screenshot(admin_page, "admin-dashboard")
        account_uuid = get_non_admin_account_uuid()

        admin_page.goto(f"/admin/impersonate/{account_uuid}")
        admin_page.wait_for_load_state("domcontentloaded")

        # Should redirect to /my/dashboard as the impersonated user
        expect(admin_page).to_have_url(f"{BASE_URL}/my/dashboard")
        screenshot(admin_page, "impersonated-user-dashboard")

        # The impersonation banner should be visible
        banner = admin_page.locator("#pre-header")
        expect(banner).to_be_visible()
        expect(banner).to_contain_text("Impersonating as")

    def test_impersonated_user_cannot_access_admin(self, admin_page: Page, screenshot):
        """A non-admin impersonated user should not access admin pages."""
        account_uuid = get_non_admin_account_uuid()

        admin_page.goto(f"/admin/impersonate/{account_uuid}")
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "impersonated-user")

        # Try to access admin dashboard as the impersonated (non-admin) user
        response = admin_page.goto("/admin/dashboard")
        assert response is not None
        screenshot(admin_page, "admin-access-denied")
        assert response.status == 403

    def test_stop_impersonation_restores_admin(self, admin_page: Page, screenshot):
        """Logging out while impersonating should restore the admin session."""
        account_uuid = get_non_admin_account_uuid()

        admin_page.goto(f"/admin/impersonate/{account_uuid}")
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "impersonating")

        # Stop impersonation via /logout (restores admin session)
        admin_page.goto("/logout")
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "after-stop-impersonation")

        # Should redirect to /admin/users (the redirect_to cookie)
        expect(admin_page).to_have_url(f"{BASE_URL}/admin/users")

        # Admin dashboard should be accessible again
        response = admin_page.goto("/admin/dashboard")
        assert response is not None
        screenshot(admin_page, "admin-restored")
        assert response.status == 200
