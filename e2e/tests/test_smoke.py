"""
Smoke tests to verify the Playwright test infrastructure works.

Run with:
    cd e2e && python -m pytest tests/test_smoke.py -v
"""

import pytest
from playwright.sync_api import Page, expect

from config import BASE_URL
from pages.login_page import LoginPage
from pages.dashboard_page import DashboardPage
from pages.admin_page import AdminPage


@pytest.mark.smoke
class TestSmoke:
    """Minimal tests that confirm the app is reachable and login works."""

    def test_homepage_loads(self, page: Page, screenshot):
        """The portal page should return HTTP 200."""
        response = page.goto("/portal")
        screenshot(page, "portal")
        assert response is not None
        assert response.status == 200

    def test_auto_login(self, authenticated_page: Page, screenshot):
        """Automatic login should redirect to the depositor dashboard."""
        screenshot(authenticated_page, "depositor-dashboard")
        expect(authenticated_page).to_have_url(f"{BASE_URL}/my/dashboard")

    def test_admin_access(self, admin_page: Page, screenshot):
        """The default dev account should have admin access."""
        screenshot(admin_page, "admin-dashboard")
        expect(admin_page).to_have_url(f"{BASE_URL}/admin/dashboard")

    def test_portal_page_title(self, page: Page, screenshot):
        """The portal page should contain a meaningful title."""
        page.goto("/portal")
        screenshot(page, "portal-with-title")
        expect(page).not_to_have_title("")


@pytest.mark.smoke
class TestPageObjects:
    """Verify that page objects can be instantiated and used."""

    def test_login_page(self, page: Page, screenshot):
        login_page = LoginPage(page)
        login_page.login_auto()
        screenshot(page, "after-auto-login")
        assert "/my/dashboard" in page.url

    def test_dashboard_page(self, authenticated_page: Page, screenshot):
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()
        screenshot(authenticated_page, "dashboard-page")
        assert "/my/dashboard" in authenticated_page.url

    def test_admin_page(self, admin_page: Page, screenshot):
        admin = AdminPage(admin_page)
        admin.navigate()
        screenshot(admin_page, "admin-page")
        assert "/admin/dashboard" in admin_page.url
