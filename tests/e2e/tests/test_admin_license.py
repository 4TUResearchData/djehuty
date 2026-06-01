"""
Admin license-change tests.

Covers:
    - /admin/update-published-dataset dashboard shows the License link
    - End-to-end license-change flow on the seeded test dataset
      (docker/sparql-init/002-seed-test-data.sql)
    - The Step 3 warning about legal implications is shown
    - Non-admin users get 403 on the page and API endpoints
    - The update endpoint rejects missing fields, unknown licenses,
      and the wrong HTTP method

Run with:
    cd tests/e2e && python -m pytest tests/test_admin_license.py -v
"""

import json

import pytest
from playwright.sync_api import Page, expect

from helpers.accounts import get_non_admin_account_uuid
from helpers.impersonation import impersonate, stop_impersonation
from pages.admin_license_page import AdminLicensePage


# Mirrors the seed dataset in docker/sparql-init/002-seed-test-data.sql.
# Shared with the search tests; the license test only mutates djht:license
# (which no other test asserts), so they can run in any order.
SEED_TITLE          = "Search Test Seed Dataset"
SEED_CONTAINER_UUID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
SEED_DOI            = f"10.4121/search-seed-{SEED_CONTAINER_UUID}"
SEED_CURRENT_URL    = "https://creativecommons.org/licenses/by-nc/4.0/"
SEED_CURRENT_NAME   = "CC BY-NC 4.0"

NEW_LICENSE_URL  = "https://creativecommons.org/licenses/by/4.0/"
NEW_LICENSE_NAME = "CC BY 4.0"


# ---------------------------------------------------------------------------
# Dashboard link
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminLicenseDashboardLink:
    """The /admin/update-published-dataset page links to license."""

    def test_dashboard_shows_license_link(self, admin_page: Page, screenshot):
        response = admin_page.goto("/admin/update-published-dataset")
        assert response is not None
        assert response.status == 200
        admin_page.wait_for_load_state("domcontentloaded")
        license_link = admin_page.locator(
            "a[href='/admin/update-published-dataset/license']"
        )
        expect(license_link).to_be_visible()
        screenshot(admin_page, "update-published-dataset-license-link")


# ---------------------------------------------------------------------------
# License change flow (uses the seeded dataset)
# ---------------------------------------------------------------------------


@pytest.mark.admin
@pytest.mark.admin_embargo
class TestAdminLicenseFlow:
    """End-to-end license-change flow against the seeded dataset."""

    def test_search_pick_preview_warning_and_confirm(
        self, admin_page: Page, screenshot
    ):
        """Search for the seeded dataset, pick a new license, review
        (verify the warning is shown), confirm, and verify the change
        persists in subsequent searches."""

        license_page = AdminLicensePage(admin_page)
        license_page.navigate()

        # Step 1.
        license_page.search(SEED_TITLE)
        license_page.wait_for_results()
        screenshot(admin_page, "license-step1-results")
        target_row = license_page.row_for_title(SEED_TITLE)
        expect(target_row.first).to_be_visible()
        license_page.select_row_by_title(SEED_TITLE)

        # Step 2 - current state.
        assert license_page.detail_value("title") == SEED_TITLE
        assert license_page.detail_value("doi") == SEED_DOI
        assert license_page.detail_value("current-name") == SEED_CURRENT_NAME
        assert license_page.detail_value("current-url") == SEED_CURRENT_URL
        assert license_page.detail_value("container-uri") == f"container:{SEED_CONTAINER_UUID}"
        screenshot(admin_page, "license-step2-detail")

        # Back-and-forth navigation works.
        license_page.click_change_dataset()
        license_page.select_row_by_title(SEED_TITLE)

        # Pick a new license, preview.
        license_page.select_license(NEW_LICENSE_URL)
        license_page.click_preview()

        # Step 3 - warning is shown and the diff matches.
        assert license_page.warning_visible()
        assert license_page.confirm_value("title") == SEED_TITLE
        assert license_page.confirm_value("from-name") == SEED_CURRENT_NAME
        assert license_page.confirm_value("from-url")  == SEED_CURRENT_URL
        assert license_page.confirm_value("to-name")   == NEW_LICENSE_NAME
        assert license_page.confirm_value("to-url")    == NEW_LICENSE_URL
        screenshot(admin_page, "license-step3-review")

        # Back-to-edit lands on Step 2 with the chosen value preserved.
        license_page.click_back()
        assert admin_page.locator("#license-select").input_value() == NEW_LICENSE_URL
        license_page.click_preview()

        license_page.click_confirm()
        expect(admin_page.locator("#license-step-1")).to_be_visible()
        screenshot(admin_page, "license-after-confirm")

        # Verify the change persists via a fresh search (clear cache so
        # the search isn't served from the stale entry written during
        # Step 1 above).
        admin_page.request.get("/admin/maintenance/clear-cache")
        license_page.search(SEED_TITLE)
        license_page.wait_for_results()
        license_page.select_row_by_title(SEED_TITLE)
        assert license_page.detail_value("current-name") == NEW_LICENSE_NAME
        assert license_page.detail_value("current-url")  == NEW_LICENSE_URL


# ---------------------------------------------------------------------------
# Access control & validation
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminLicenseAccessControl:
    """Non-admin users cannot reach the license page or APIs."""

    @pytest.mark.parametrize(
        "path",
        ["/admin/update-published-dataset/license"],
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
            "/admin/update-published-dataset/license/search",
            data=json.dumps({"search_for": "anything"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403
        stop_impersonation(admin_page)

    def test_non_admin_gets_403_on_update_api(self, admin_page: Page):
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)
        response = admin_page.request.fetch(
            "/admin/update-published-dataset/license/update",
            method="PUT",
            data=json.dumps({
                "container_uri":    "container:00000000-0000-0000-0000-000000000000",
                "dataset_uri":      "dataset:00000000-0000-0000-0000-000000000000",
                "new_license_url":  NEW_LICENSE_URL,
            }),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403
        stop_impersonation(admin_page)

    def test_update_api_rejects_missing_fields(self, admin_page: Page):
        response = admin_page.request.fetch(
            "/admin/update-published-dataset/license/update",
            method="PUT",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400

    def test_update_api_rejects_unknown_license(self, admin_page: Page):
        response = admin_page.request.fetch(
            "/admin/update-published-dataset/license/update",
            method="PUT",
            data=json.dumps({
                "container_uri":    "container:00000000-0000-0000-0000-000000000000",
                "dataset_uri":      "dataset:00000000-0000-0000-0000-000000000000",
                "new_license_url":  "https://example.invalid/not-a-real-license/",
            }),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400

    def test_update_api_rejects_wrong_method(self, admin_page: Page):
        response = admin_page.request.post(
            "/admin/update-published-dataset/license/update",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 405
