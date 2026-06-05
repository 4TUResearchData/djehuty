"""
Admin embargo management tests.

Covers:
    - "Update Published Dataset" submenu entry appears on admin pages
    - /admin/update-published-dataset dashboard shows the Embargos link
    - End-to-end embargo workflow: search → select → update → persist
    - Non-admin users get 403 on the page and API endpoints

Run with:
    cd tests/e2e && python -m pytest tests/test_admin_embargo.py -v
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from helpers.accounts import get_non_admin_account_uuid
from helpers.dataset import create_draft_dataset, get_container_uuid_from_url
from helpers.impersonation import impersonate, stop_impersonation
from helpers.publish import fill_required_fields_and_publish
from pages.admin_embargo_page import AdminEmbargoPage
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


EMBARGO_TITLE = "Admin Embargo Management E2E"
INITIAL_EMBARGO_DAYS = 365


def _iso_date(offset_days: int) -> str:
    return (date.today() + timedelta(days=offset_days)).isoformat()


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    file_path = tmp_path / "admin-embargo-test-file.txt"
    file_path.write_bytes(b"Admin embargo test file.\n")
    return str(file_path)


@pytest.fixture()
def embargoed_dataset(authenticated_page: Page, test_file: str):
    """Create and publish an embargoed dataset with a known title."""
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(test_file)
    editor.save()

    fill_required_fields_and_publish(
        authenticated_page,
        container_uuid,
        title=EMBARGO_TITLE,
        is_embargoed=True,
        embargo_until_date=_iso_date(INITIAL_EMBARGO_DAYS),
    )

    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")
    return container_uuid


# ---------------------------------------------------------------------------
# Submenu / dashboard
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminUpdatePublishedDatasetDashboard:
    """Verify the /admin/update-published-dataset page and its submenu link."""

    def test_submenu_entry_visible_on_admin_dashboard(self, admin_page: Page, screenshot):
        """The 'Update Published Dataset' link should appear in the admin submenu."""
        screenshot(admin_page, "admin-dashboard")
        expect(
            admin_page.locator("a[href='/admin/update-published-dataset']")
        ).to_be_visible()

    def test_dashboard_shows_embargos_link(self, admin_page: Page, screenshot):
        """The dashboard should be reachable and show the Embargos action link."""
        response = admin_page.goto("/admin/update-published-dataset")
        assert response is not None
        assert response.status == 200
        admin_page.wait_for_load_state("domcontentloaded")
        embargos_link = admin_page.locator(
            "a[href='/admin/update-published-dataset/embargos']"
        )
        expect(embargos_link).to_be_visible()
        screenshot(admin_page, "update-published-dataset-embargos-link")


# ---------------------------------------------------------------------------
# Embargo management page
# ---------------------------------------------------------------------------


@pytest.mark.admin
@pytest.mark.admin_embargo
class TestAdminEmbargoManagement:
    """Verify the embargo management page, search, and update flows."""

    def test_search_select_and_update_embargo(
        self, embargoed_dataset, admin_page: Page, screenshot
    ):
        """End-to-end: search for the embargoed dataset, select it (Step 1),
        set a new embargo date (Step 2), preview & confirm (Step 3), and
        verify the change persists."""
        initial_date = _iso_date(INITIAL_EMBARGO_DAYS)
        new_date = _iso_date(30)

        embargo_page = AdminEmbargoPage(admin_page)
        embargo_page.navigate()

        # Step 1: search & select.
        embargo_page.search(EMBARGO_TITLE)
        embargo_page.wait_for_results()
        screenshot(admin_page, "embargos-step1-search-results")

        target_row = embargo_page.row_for_title(EMBARGO_TITLE)
        expect(target_row.first).to_be_visible()
        embargo_page.select_row_by_title(EMBARGO_TITLE)

        # Step 2: dataset detail + new date.
        screenshot(admin_page, "embargos-step2-edit")
        assert embargo_page.detail_value("title") == EMBARGO_TITLE
        assert embargo_page.detail_value("embargo-date") == initial_date
        date_input = admin_page.locator("#embargo-date-input")
        assert date_input.input_value() == initial_date

        # "Change dataset" goes back to Step 1, then we re-select.
        embargo_page.click_change_dataset()
        embargo_page.select_row_by_title(EMBARGO_TITLE)

        embargo_page.set_embargo_date(new_date)
        embargo_page.click_preview()

        # Step 3: preview & confirm.
        screenshot(admin_page, "embargos-step3-preview")
        assert embargo_page.confirm_value("title") == EMBARGO_TITLE
        assert embargo_page.confirm_value("from-date") == initial_date
        assert embargo_page.confirm_value("to-date") == new_date

        # "Back to edit" returns to Step 2, then preview again.
        embargo_page.click_back_to_edit()
        assert admin_page.locator("#embargo-date-input").input_value() == new_date
        embargo_page.click_preview()

        embargo_page.click_confirm()
        screenshot(admin_page, "embargos-after-confirm")

        # After confirm, the page returns to Step 1 with a success message.
        expect(admin_page.locator("#embargo-step-1")).to_be_visible()

        # Reload and search again to confirm persistence.
        embargo_page.navigate()
        embargo_page.search(EMBARGO_TITLE)
        embargo_page.wait_for_results()
        embargo_page.select_row_by_title(EMBARGO_TITLE)
        assert embargo_page.detail_value("embargo-date") == new_date


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminEmbargoAccessControl:
    """Verify non-admin users cannot reach the embargo page or APIs."""

    @pytest.mark.parametrize(
        "path",
        [
            "/admin/update-published-dataset",
            "/admin/update-published-dataset/embargos",
        ],
    )
    def test_non_admin_gets_403_on_page(self, admin_page: Page, screenshot, path):
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)

        response = admin_page.goto(path)
        assert response is not None
        screenshot(admin_page, f"non-admin-{path.strip('/').replace('/', '-')}-403")
        assert response.status == 403

        stop_impersonation(admin_page)

    def test_non_admin_gets_403_on_search_api(self, admin_page: Page):
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)

        response = admin_page.request.post(
            "/admin/update-published-dataset/embargos/search",
            data=json.dumps({"search_for": "anything"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403

        stop_impersonation(admin_page)

    def test_non_admin_gets_403_on_update_api(self, admin_page: Page):
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)

        response = admin_page.request.fetch(
            "/admin/update-published-dataset/embargos/update",
            method="PUT",
            data=json.dumps({
                "dataset_uuid": "00000000-0000-0000-0000-000000000000",
                "embargo_until_date": _iso_date(1),
            }),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403

        stop_impersonation(admin_page)

    def test_update_api_rejects_missing_fields(self, admin_page: Page):
        """Admin call with missing fields should return 400."""
        response = admin_page.request.fetch(
            "/admin/update-published-dataset/embargos/update",
            method="PUT",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400

    def test_update_api_rejects_wrong_method(self, admin_page: Page):
        """The update endpoint only accepts PUT."""
        response = admin_page.request.post(
            "/admin/update-published-dataset/embargos/update",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 405
