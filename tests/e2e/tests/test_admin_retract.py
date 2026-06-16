"""
Admin retract dataset tests.

Covers:
    - /admin/update-published-dataset dashboard shows the Retract link
    - End-to-end retract flow on the seeded test dataset
      (docker/sparql-init/002-seed-test-data.sql)
    - The Confirm button is disabled until the DOI is typed correctly
    - Non-admin users get 403 on the page and API endpoints
    - The execute endpoint rejects missing fields and DOI mismatches

Run with:
    cd tests/e2e && python -m pytest tests/test_admin_retract.py -v
"""

import json

import pytest
from playwright.sync_api import Page, expect

from helpers.accounts import get_non_admin_account_uuid
from helpers.impersonation import impersonate, stop_impersonation
from pages.admin_retract_page import AdminRetractPage


# Mirrors the second INSERT block in
# docker/sparql-init/002-seed-test-data.sql. If any value here changes,
# update the seed accordingly (and vice versa).
SEED_TITLE          = "Retract Test Seed Dataset"
SEED_CONTAINER_UUID = "11111111-2222-3333-8444-555555555555"
SEED_DOI            = f"10.4121/retract-seed-{SEED_CONTAINER_UUID}"


# ---------------------------------------------------------------------------
# Dashboard link
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminRetractDashboardLink:
    """The /admin/update-published-dataset page links to retract."""

    def test_dashboard_shows_retract_link(self, admin_page: Page, screenshot):
        response = admin_page.goto("/admin/update-published-dataset")
        assert response is not None
        assert response.status == 200
        admin_page.wait_for_load_state("domcontentloaded")
        retract_link = admin_page.locator(
            "a[href='/admin/update-published-dataset/retract']"
        )
        expect(retract_link).to_be_visible()
        screenshot(admin_page, "update-published-dataset-retract-link")


# ---------------------------------------------------------------------------
# Retract flow (uses the seeded dataset)
# ---------------------------------------------------------------------------


@pytest.mark.admin
@pytest.mark.admin_retract
class TestAdminRetractFlow:
    """End-to-end retract flow against the seeded "Retract Test Seed Dataset"."""

    def test_search_preview_doi_gate_and_confirm(
        self, admin_page: Page, screenshot
    ):
        """Search for the seeded dataset, preview, exercise the DOI gate,
        confirm, and verify the post-retraction state."""

        retract_page = AdminRetractPage(admin_page)
        retract_page.navigate()

        # Step 1.
        retract_page.search(SEED_TITLE)
        retract_page.wait_for_results()
        screenshot(admin_page, "retract-step1-results")
        target_row = retract_page.row_for_title(SEED_TITLE)
        expect(target_row.first).to_be_visible()
        retract_page.select_row_by_title(SEED_TITLE)

        # Step 2.
        assert retract_page.detail_value("title") == SEED_TITLE
        assert retract_page.detail_value("doi") == SEED_DOI
        assert retract_page.detail_value("container-uuid") == SEED_CONTAINER_UUID
        screenshot(admin_page, "retract-step2-detail")

        # Back-and-forth navigation works.
        retract_page.click_change_dataset()
        retract_page.select_row_by_title(SEED_TITLE)
        retract_page.click_preview()

        # Step 3 - the Confirm button starts disabled.
        assert "disabled" in (retract_page.confirm_button().get_attribute("class") or "")

        # A wrong value does not enable Confirm.
        retract_page.type_doi_confirmation("not-the-doi")
        assert "disabled" in (retract_page.confirm_button().get_attribute("class") or "")

        # Typing the correct DOI enables Confirm.
        retract_page.type_doi_confirmation(SEED_DOI)
        classes = retract_page.confirm_button().get_attribute("class") or ""
        assert "disabled" not in classes
        screenshot(admin_page, "retract-step3-doi-typed")

        retract_page.click_confirm()
        # After success the UI returns to Step 1.
        expect(admin_page.locator("#retract-step-1")).to_be_visible()
        screenshot(admin_page, "retract-after-confirm")

        # The retracted dataset should no longer be returned by the search
        # endpoint that filters by is_published + is_latest. admin_retract_dataset
        # already invalidates the "datasets" cache, but force a clear here for
        # belt-and-braces in case a fresh entry got cached by the prior search.
        admin_page.request.get("/admin/maintenance/clear-cache")
        retract_page.search(SEED_TITLE)
        rows = admin_page.locator("#retract-results-body tr")
        expect(rows).to_have_count(0)


# ---------------------------------------------------------------------------
# Access control & validation
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminRetractAccessControl:
    """Non-admin users cannot reach the retract page or APIs."""

    @pytest.mark.parametrize(
        "path",
        ["/admin/update-published-dataset/retract"],
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
            "/admin/update-published-dataset/retract/search",
            data=json.dumps({"search_for": "anything"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403
        stop_impersonation(admin_page)

    def test_non_admin_gets_403_on_execute_api(self, admin_page: Page):
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)
        response = admin_page.request.fetch(
            "/admin/update-published-dataset/retract/execute",
            method="PUT",
            data=json.dumps({
                "container_uuid": "00000000-0000-0000-0000-000000000000",
                "dataset_uuid":   "00000000-0000-0000-0000-000000000000",
                "confirm_doi":    "10.0/x",
                "expected_doi":   "10.0/x",
            }),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403
        stop_impersonation(admin_page)

    def test_execute_api_rejects_missing_fields(self, admin_page: Page):
        response = admin_page.request.fetch(
            "/admin/update-published-dataset/retract/execute",
            method="PUT",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400

    def test_execute_api_rejects_doi_mismatch(self, admin_page: Page):
        response = admin_page.request.fetch(
            "/admin/update-published-dataset/retract/execute",
            method="PUT",
            data=json.dumps({
                "container_uuid": "00000000-0000-0000-0000-000000000000",
                "dataset_uuid":   "00000000-0000-0000-0000-000000000000",
                "confirm_doi":    "wrong",
                "expected_doi":   "right",
            }),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400

    def test_execute_api_rejects_wrong_method(self, admin_page: Page):
        response = admin_page.request.post(
            "/admin/update-published-dataset/retract/execute",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 405
