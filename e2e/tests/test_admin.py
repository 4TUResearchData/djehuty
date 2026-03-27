"""
Administration panel tests.

Covers:
    - Access admin dashboard as admin user
    - Verify non-admin gets 403
    - Navigate admin sub-pages (users, reports, quota requests)
    - Reports pages (restricted datasets, embargoed datasets)
    - Quota request approve/deny through UI

Run with:
    cd e2e && python -m pytest tests/test_admin.py -v
"""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from config import BASE_URL
from helpers.accounts import get_non_admin_account_uuid
from helpers.dataset import create_draft_dataset, get_container_uuid_from_url
from helpers.impersonation import impersonate, stop_impersonation
from helpers.publish import fill_required_fields_and_publish
from helpers.quota import create_quota_request
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    """Create a temporary test file and return its path."""
    file_path = tmp_path / "admin-test-file.txt"
    file_path.write_bytes(b"Admin report test file.\n")
    return str(file_path)


@pytest.fixture()
def restricted_dataset(authenticated_page: Page, test_file: str):
    """Create and publish a restricted dataset for admin report tests."""
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(test_file)
    editor.save()

    fill_required_fields_and_publish(
        authenticated_page,
        container_uuid,
        title="Restricted Dataset for Admin Report",
        is_restricted=True,
    )

    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")
    return container_uuid


@pytest.fixture()
def embargoed_dataset(authenticated_page: Page, test_file: str):
    """Create and publish an embargoed dataset for admin report tests."""
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(test_file)
    editor.save()

    fill_required_fields_and_publish(
        authenticated_page,
        container_uuid,
        title="Embargoed Dataset for Admin Report",
        is_embargoed=True,
    )

    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")
    return container_uuid


# ---------------------------------------------------------------------------
# Admin dashboard access
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminDashboard:
    """Verify admin dashboard access and basic navigation."""

    def test_admin_dashboard_accessible(self, admin_page: Page, screenshot):
        """Admin user should see the administration dashboard."""
        screenshot(admin_page, "admin-dashboard")
        expect(admin_page.locator("body")).to_contain_text("Administration dashboard")

    def test_admin_dashboard_has_navigation(self, admin_page: Page, screenshot):
        """Admin dashboard should show navigation links to sub-pages."""
        screenshot(admin_page, "admin-nav-links")
        expect(admin_page.locator("a[href='/admin/users']")).to_be_visible()
        expect(admin_page.locator("a[href='/admin/reports']")).to_be_visible()

    def test_admin_dashboard_has_maintenance_buttons(self, admin_page: Page, screenshot):
        """Admin dashboard should display maintenance action buttons."""
        expect(admin_page.locator("#clear-cache")).to_be_visible()
        expect(admin_page.locator("#clear-website-sessions")).to_be_visible()
        expect(admin_page.locator("#recalculate-statistics")).to_be_visible()
        screenshot(admin_page, "maintenance-buttons")

    def test_non_admin_gets_403(self, admin_page: Page, screenshot):
        """A non-admin user should receive 403 on /admin/dashboard."""
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)
        screenshot(admin_page, "impersonated-non-admin")

        response = admin_page.goto("/admin/dashboard")
        assert response is not None
        screenshot(admin_page, "non-admin-dashboard-403")
        assert response.status == 403

        # Restore admin session
        stop_impersonation(admin_page)


# ---------------------------------------------------------------------------
# Admin sub-pages
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminUsers:
    """Verify the admin users page."""

    def test_users_page_accessible(self, admin_page: Page, screenshot):
        """Admin should be able to access /admin/users."""
        response = admin_page.goto("/admin/users")
        assert response is not None
        assert response.status == 200
        screenshot(admin_page, "admin-users")
        expect(admin_page.locator("body")).to_contain_text("Manage users")

    def test_users_table_visible(self, admin_page: Page, screenshot):
        """The users table should be present and contain at least one row."""
        admin_page.goto("/admin/users")
        admin_page.wait_for_load_state("domcontentloaded")
        users_table = admin_page.locator("#users-table")
        expect(users_table).to_be_visible()
        screenshot(admin_page, "users-table")

        # Should have at least one user row
        rows = users_table.locator("tbody tr")
        assert rows.count() > 0

    def test_users_page_has_impersonate_links(self, admin_page: Page, screenshot):
        """User rows should have impersonation action links."""
        admin_page.goto("/admin/users")
        admin_page.wait_for_load_state("domcontentloaded")

        impersonate_links = admin_page.locator("a[href*='/admin/impersonate/']")
        screenshot(admin_page, "impersonate-links")
        assert impersonate_links.count() > 0

    def test_non_admin_gets_403(self, admin_page: Page, screenshot):
        """A non-admin user should receive 403 on /admin/users."""
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)

        response = admin_page.goto("/admin/users")
        assert response is not None
        screenshot(admin_page, "non-admin-users-403")
        assert response.status == 403

        stop_impersonation(admin_page)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminReports:
    """Verify admin reports pages."""

    def test_reports_dashboard_accessible(self, admin_page: Page, screenshot):
        """Admin should be able to access /admin/reports."""
        response = admin_page.goto("/admin/reports")
        assert response is not None
        assert response.status == 200
        screenshot(admin_page, "reports-dashboard")
        expect(admin_page.locator("body")).to_contain_text("Reports")

    def test_reports_dashboard_has_report_links(self, admin_page: Page, screenshot):
        """Reports dashboard should link to individual report pages."""
        admin_page.goto("/admin/reports")
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "reports-links")

        expect(
            admin_page.locator("a[href='/admin/reports/restricted_datasets']")
        ).to_be_visible()
        expect(
            admin_page.locator("a[href='/admin/reports/embargoed_datasets']")
        ).to_be_visible()

    def test_restricted_datasets_report(self, admin_page: Page, screenshot):
        """Admin should be able to view the restricted datasets report."""
        response = admin_page.goto("/admin/reports/restricted_datasets")
        assert response is not None
        assert response.status == 200
        screenshot(admin_page, "restricted-datasets-report")
        expect(admin_page.locator("body")).to_contain_text("Restricted Datasets")

    def test_embargoed_datasets_report(self, admin_page: Page, screenshot):
        """Admin should be able to view the embargoed datasets report."""
        response = admin_page.goto("/admin/reports/embargoed_datasets")
        assert response is not None
        assert response.status == 200
        screenshot(admin_page, "embargoed-datasets-report")
        expect(admin_page.locator("body")).to_contain_text("Embargoed Datasets")

    def test_restricted_report_has_export_links(self, restricted_dataset, admin_page: Page, screenshot):
        """Restricted datasets report should have CSV and JSON export links."""
        admin_page.goto("/admin/reports/restricted_datasets")
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "restricted-export-links")

        expect(
            admin_page.locator("a[href*='export=1'][href*='format=csv']")
        ).to_be_visible()
        expect(
            admin_page.locator("a[href*='export=1'][href*='format=json']")
        ).to_be_visible()

    def test_embargoed_report_has_export_links(self, embargoed_dataset, admin_page: Page, screenshot):
        """Embargoed datasets report should have CSV and JSON export links."""
        admin_page.goto("/admin/reports/embargoed_datasets")
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "embargoed-export-links")

        expect(
            admin_page.locator("a[href*='export=1'][href*='format=csv']")
        ).to_be_visible()
        expect(
            admin_page.locator("a[href*='export=1'][href*='format=json']")
        ).to_be_visible()

    def test_non_admin_gets_403_on_reports(self, admin_page: Page, screenshot):
        """A non-admin user should receive 403 on /admin/reports."""
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)

        response = admin_page.goto("/admin/reports")
        assert response is not None
        screenshot(admin_page, "non-admin-reports-403")
        assert response.status == 403

        stop_impersonation(admin_page)

    def test_non_admin_gets_403_on_restricted_report(self, admin_page: Page, screenshot):
        """A non-admin user should receive 403 on restricted datasets report."""
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)

        response = admin_page.goto("/admin/reports/restricted_datasets")
        assert response is not None
        screenshot(admin_page, "non-admin-restricted-403")
        assert response.status == 403

        stop_impersonation(admin_page)


# ---------------------------------------------------------------------------
# Quota requests
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminQuotaRequests:
    """Verify quota request management through the admin UI."""

    def test_quota_requests_page_accessible(self, admin_page: Page, screenshot):
        """Admin should be able to access /admin/quota-requests."""
        response = admin_page.goto("/admin/quota-requests")
        assert response is not None
        assert response.status == 200
        screenshot(admin_page, "quota-requests-page")
        expect(admin_page.locator("body")).to_contain_text("Quota requests")

    def test_approve_quota_request(self, admin_page: Page, screenshot):
        """Admin should be able to approve a pending quota request."""
        # Create a quota request as the authenticated user
        create_quota_request(admin_page, quota_gb=5, reason="Need more space for E2E test")

        admin_page.goto("/admin/quota-requests")
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "quota-before-approve")

        # Verify the request appears in the table
        quotas_table = admin_page.locator("#quotas-table")
        expect(quotas_table).to_be_visible()
        expect(quotas_table).to_contain_text("5.0 GB")

        # Click approve (thumbs up) on the first row
        approve_link = admin_page.locator(
            "a[href*='/admin/approve-quota-request/']"
        ).first
        approve_link.click()
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "quota-after-approve")

        # Should redirect back to quota requests page
        expect(admin_page).to_have_url(f"{BASE_URL}/admin/quota-requests")

    def test_deny_quota_request(self, admin_page: Page, screenshot):
        """Admin should be able to deny a pending quota request."""
        # Create a quota request
        create_quota_request(admin_page, quota_gb=100, reason="Deny test request")

        admin_page.goto("/admin/quota-requests")
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "quota-before-deny")

        quotas_table = admin_page.locator("#quotas-table")
        expect(quotas_table).to_contain_text("100.0 GB")

        # Click deny (thumbs down)
        deny_link = admin_page.locator(
            "a[href*='/admin/deny-quota-request/']"
        ).first
        deny_link.click()
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "quota-after-deny")

        # Should redirect back to quota requests page
        expect(admin_page).to_have_url(f"{BASE_URL}/admin/quota-requests")

    def test_non_admin_gets_403_on_quota_requests(self, admin_page: Page, screenshot):
        """A non-admin user should receive 403 on /admin/quota-requests."""
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)

        response = admin_page.goto("/admin/quota-requests")
        assert response is not None
        screenshot(admin_page, "non-admin-quota-403")
        assert response.status == 403

        stop_impersonation(admin_page)
