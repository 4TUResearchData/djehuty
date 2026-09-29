"""
Admin remove-files-from-version tests.

Covers:
    - /admin/update-published-dataset dashboard shows the Remove files link
    - End-to-end remove-files flow on the seeded test dataset
      (docker/sparql-init/002-seed-test-data.sql)
    - The Continue button is disabled until a file is ticked
    - The Remove button is disabled until the DOI is typed correctly
    - Non-admin users get 403 on the page and API endpoints
    - The execute endpoint rejects missing fields, DOI mismatches, unknown
      files and the wrong method

Run with:
    cd tests/e2e && python -m pytest tests/test_admin_remove_files.py -v
"""

import json

import pytest
from helpers.accounts import get_non_admin_account_uuid
from helpers.impersonation import impersonate, stop_impersonation
from pages.admin_remove_files_page import AdminRemoveFilesPage
from playwright.sync_api import Page, expect

# Mirrors the third INSERT block in
# docker/sparql-init/002-seed-test-data.sql. If any value here changes,
# update the seed accordingly (and vice versa).
SEED_TITLE = "Remove Files Test Seed Dataset"
SEED_CONTAINER_UUID = "c0ffee00-0000-4000-8000-000000000001"
SEED_DATASET_UUID = "c0ffee00-0000-4000-8000-000000000002"
SEED_DOI = f"10.4121/remove-files-seed-{SEED_CONTAINER_UUID}"
REMOVE_FILE_NAME = "remove-me.csv"
KEEP_FILE_NAME = "keep-me.txt"

FILES_URL = "/admin/update-published-dataset/remove-files/files"
VERSIONS_URL = "/admin/update-published-dataset/remove-files/versions"
EXECUTE_URL = "/admin/update-published-dataset/remove-files/execute"


# ---------------------------------------------------------------------------
# Dashboard link
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminRemoveFilesDashboardLink:
    """The /admin/update-published-dataset page links to remove-files."""

    def test_dashboard_shows_remove_files_link(self, admin_page: Page, screenshot):
        response = admin_page.goto("/admin/update-published-dataset")
        assert response is not None
        assert response.status == 200
        admin_page.wait_for_load_state("domcontentloaded")
        link = admin_page.locator("a[href='/admin/update-published-dataset/remove-files']")
        expect(link).to_be_visible()
        screenshot(admin_page, "update-published-dataset-remove-files-link")


# ---------------------------------------------------------------------------
# Remove-files flow (uses the seeded dataset)
# ---------------------------------------------------------------------------


@pytest.mark.admin
@pytest.mark.admin_remove_files
class TestAdminRemoveFilesFlow:
    """End-to-end flow against the seeded "Remove Files Test Seed Dataset"."""

    def test_search_select_file_doi_gate_and_confirm(self, admin_page: Page, screenshot):
        """Search, pick the version, select a file, exercise the two gates
        (Continue and DOI), remove, and verify the file is gone."""

        page = AdminRemoveFilesPage(admin_page)
        page.navigate()

        # Step 1.
        page.search(SEED_TITLE)
        page.wait_for_results()
        screenshot(admin_page, "remove-files-step1-results")
        expect(page.row_for_title(SEED_TITLE).first).to_be_visible()
        page.select_dataset_by_title(SEED_TITLE)

        # Step 2 - single published version.
        expect(page.version_rows()).to_have_count(1)
        screenshot(admin_page, "remove-files-step2-versions")
        page.select_first_version()

        # Step 3 - both seeded files are listed.
        expect(page.file_rows()).to_have_count(2)
        screenshot(admin_page, "remove-files-step3-files")

        # Continue starts disabled until a file is ticked.
        assert "disabled" in (page.continue_button().get_attribute("class") or "")
        page.select_file_by_name(REMOVE_FILE_NAME)
        assert "disabled" not in (page.continue_button().get_attribute("class") or "")
        page.click_continue()

        # Step 4 - review lists only the ticked file.
        confirmed = " ".join(page.confirm_file_names())
        assert REMOVE_FILE_NAME in confirmed
        assert KEEP_FILE_NAME not in confirmed

        # Remove starts disabled; a wrong DOI keeps it disabled.
        assert "disabled" in (page.confirm_button().get_attribute("class") or "")
        page.type_doi_confirmation("not-the-doi")
        assert "disabled" in (page.confirm_button().get_attribute("class") or "")

        # The correct DOI enables Remove.
        page.type_doi_confirmation(SEED_DOI)
        assert "disabled" not in (page.confirm_button().get_attribute("class") or "")
        screenshot(admin_page, "remove-files-step4-doi-typed")

        page.click_confirm()
        # After success the UI returns to Step 1.
        expect(admin_page.locator("#rmf-step-1")).to_be_visible()
        screenshot(admin_page, "remove-files-after-confirm")

        # The removed file is detached; the kept file stays. Clear the cache
        # first for belt-and-braces (execute already invalidates it).
        admin_page.request.get("/admin/maintenance/clear-cache")
        response = admin_page.request.post(
            FILES_URL,
            data=json.dumps(
                {"container_uuid": SEED_CONTAINER_UUID, "dataset_uuid": SEED_DATASET_UUID}
            ),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 200
        files = response.json()
        names = [f.get("name") for f in files]
        assert names == [KEEP_FILE_NAME]


# ---------------------------------------------------------------------------
# Access control & validation
# ---------------------------------------------------------------------------


@pytest.mark.admin
class TestAdminRemoveFilesAccessControl:
    """Non-admin users cannot reach the page or APIs; execute validates input."""

    def test_non_admin_gets_403_on_page(self, admin_page: Page, screenshot):
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)
        response = admin_page.goto("/admin/update-published-dataset/remove-files")
        assert response is not None
        screenshot(admin_page, "non-admin-remove-files-403")
        assert response.status == 403
        stop_impersonation(admin_page)

    def test_non_admin_gets_403_on_versions_api(self, admin_page: Page):
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)
        response = admin_page.request.post(
            VERSIONS_URL,
            data=json.dumps({"container_uuid": SEED_CONTAINER_UUID}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403
        stop_impersonation(admin_page)

    def test_non_admin_gets_403_on_files_api(self, admin_page: Page):
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)
        response = admin_page.request.post(
            FILES_URL,
            data=json.dumps(
                {"container_uuid": SEED_CONTAINER_UUID, "dataset_uuid": SEED_DATASET_UUID}
            ),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403
        stop_impersonation(admin_page)

    def test_non_admin_gets_403_on_execute_api(self, admin_page: Page):
        account_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, account_uuid)
        response = admin_page.request.fetch(
            EXECUTE_URL,
            method="PUT",
            data=json.dumps(
                {
                    "container_uuid": SEED_CONTAINER_UUID,
                    "dataset_uuid": SEED_DATASET_UUID,
                    "confirm_doi": SEED_DOI,
                    "expected_doi": SEED_DOI,
                    "file_uuids": ["00000000-0000-4000-8000-000000000000"],
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403
        stop_impersonation(admin_page)

    def test_execute_api_rejects_missing_fields(self, admin_page: Page):
        response = admin_page.request.fetch(
            EXECUTE_URL,
            method="PUT",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400

    def test_execute_api_rejects_doi_mismatch(self, admin_page: Page):
        response = admin_page.request.fetch(
            EXECUTE_URL,
            method="PUT",
            data=json.dumps(
                {
                    "container_uuid": SEED_CONTAINER_UUID,
                    "dataset_uuid": SEED_DATASET_UUID,
                    "confirm_doi": "wrong",
                    "expected_doi": "right",
                    "file_uuids": ["00000000-0000-4000-8000-000000000000"],
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400

    def test_execute_api_rejects_unknown_file(self, admin_page: Page):
        """A correctly confirmed DOI but a file that is not part of the
        version is rejected before anything is removed."""
        response = admin_page.request.fetch(
            EXECUTE_URL,
            method="PUT",
            data=json.dumps(
                {
                    "container_uuid": SEED_CONTAINER_UUID,
                    "dataset_uuid": SEED_DATASET_UUID,
                    "confirm_doi": SEED_DOI,
                    "expected_doi": SEED_DOI,
                    "file_uuids": ["00000000-0000-4000-8000-000000000000"],
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400

    def test_execute_api_rejects_wrong_method(self, admin_page: Page):
        response = admin_page.request.post(
            EXECUTE_URL,
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 405
