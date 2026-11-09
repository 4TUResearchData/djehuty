"""
Admin retract dataset tests.

Covers:
    - /admin/update-published-dataset dashboard shows the Retract link
    - End-to-end retract flow on the seeded test datasets
      (docker/sparql-init/002-seed-test-data.sql)
    - Retracting a single-version dataset, an older version only, and the
      latest version only (each scenario mutates its own seed)
    - The Confirm button is disabled until the DOI is typed correctly
    - Non-admin users get 403 on the page and API endpoints
    - The execute endpoint rejects missing fields, a missing or invalid
      version selection, an unknown version and DOI mismatches

Run with:
    cd tests/e2e && python -m pytest tests/test_admin_retract.py -v
"""

import json

import pytest
from helpers.accounts import get_non_admin_account_uuid
from helpers.impersonation import impersonate, stop_impersonation
from pages.admin_retract_page import AdminRetractPage
from playwright.sync_api import Page, expect

# Mirrors the second INSERT block in
# docker/sparql-init/002-seed-test-data.sql. If any value here changes,
# update the seed accordingly (and vice versa).
SEED_TITLE = "Retract Test Seed Dataset"
SEED_CONTAINER_UUID = "11111111-2222-3333-8444-555555555555"
SEED_DOI = f"10.4121/retract-seed-{SEED_CONTAINER_UUID}"

MULTI_SEEDS = {
    "older": {
        "title": "Retract Multi Seed One",
        "container": "a4b15000-0001-4000-8000-010000000000",
        "versions": [f"a4b15000-0001-4000-8000-02{n:010x}" for n in (1, 2, 3)],
    },
    "latest": {
        "title": "Retract Multi Seed Two",
        "container": "a4b15000-0002-4000-8000-010000000000",
        "versions": [f"a4b15000-0002-4000-8000-02{n:010x}" for n in (1, 2, 3)],
    },
}


def multi_doi(scenario: str) -> str:
    seed = 1 if scenario == "older" else 2
    return f"10.4121/retract-multi-{seed}-{MULTI_SEEDS[scenario]['container']}"


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
        retract_link = admin_page.locator("a[href='/admin/update-published-dataset/retract']")
        expect(retract_link).to_be_visible()
        screenshot(admin_page, "update-published-dataset-retract-link")


# ---------------------------------------------------------------------------
# Retract flow (uses the seeded dataset)
# ---------------------------------------------------------------------------


@pytest.mark.admin
@pytest.mark.admin_retract
class TestAdminRetractFlow:
    """End-to-end retract flow against the seeded "Retract Test Seed Dataset"."""

    def test_search_preview_doi_gate_and_confirm(self, admin_page: Page, screenshot):
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

        # Continue stays disabled until a version is ticked.
        expect(retract_page.version_rows()).to_have_count(1)
        assert "disabled" in (retract_page.preview_button().get_attribute("class") or "")

        # Back-and-forth navigation works.
        retract_page.click_change_dataset()
        retract_page.select_row_by_title(SEED_TITLE)
        retract_page.select_version(1)
        retract_page.click_preview()
        assert retract_page.confirm_value("versions") == "v1"

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
# Subset retract (one multi-version seed per scenario)
# ---------------------------------------------------------------------------


@pytest.mark.admin
@pytest.mark.admin_retract
class TestAdminRetractSubset:
    """Retract some versions of a three-version dataset. Each scenario
    retracts from its own seed because a retract cannot be undone."""

    @staticmethod
    def _open_versions(admin_page: Page, scenario: str) -> AdminRetractPage:
        title = MULTI_SEEDS[scenario]["title"]
        retract_page = AdminRetractPage(admin_page)
        retract_page.navigate()
        retract_page.search(title)
        retract_page.wait_for_results()
        retract_page.select_row_by_title(title)
        expect(retract_page.version_rows()).to_have_count(3)
        return retract_page

    @staticmethod
    def _confirm_and_reopen(admin_page: Page, retract_page: AdminRetractPage, scenario: str):
        title = MULTI_SEEDS[scenario]["title"]
        retract_page.type_doi_confirmation(multi_doi(scenario))
        retract_page.click_confirm()
        expect(admin_page.locator("#retract-step-1")).to_be_visible()
        admin_page.request.get("/admin/maintenance/clear-cache")
        retract_page.search(title)
        retract_page.wait_for_results()
        retract_page.select_row_by_title(title)

    def test_retract_older_version_keeps_latest_public(self, admin_page: Page, screenshot):
        retract_page = self._open_versions(admin_page, "older")

        retract_page.select_version(1)
        assert retract_page.selected_version_count() == 1
        retract_page.click_preview()
        assert retract_page.confirm_value("versions") == "v1"
        summary = admin_page.locator("#retract-summary-list").inner_text()
        assert "v3 stays public" in summary
        screenshot(admin_page, "retract-subset-older-step3")

        self._confirm_and_reopen(admin_page, retract_page, "older")
        expect(retract_page.version_rows()).to_have_count(2)
        expect(retract_page.version_row(1)).to_have_count(0)
        screenshot(admin_page, "retract-subset-older-after")

        container = MULTI_SEEDS["older"]["container"]
        tombstone = admin_page.request.get(
            f"/datasets/{container}/1", headers={"Accept": "text/html"}
        )
        assert tombstone.status == 410
        assert f"{multi_doi('older')}.v1" in tombstone.text()

    def test_retract_latest_version_drafts_it_and_promotes_previous(
        self, admin_page: Page, screenshot
    ):
        retract_page = self._open_versions(admin_page, "latest")

        retract_page.select_version(3)
        retract_page.click_preview()
        assert retract_page.confirm_value("versions") == "v3"
        summary = admin_page.locator("#retract-summary-list").inner_text()
        assert "v3 (latest) becomes a draft" in summary
        assert "v2 stays public" in summary
        screenshot(admin_page, "retract-subset-latest-step3")

        self._confirm_and_reopen(admin_page, retract_page, "latest")
        expect(retract_page.version_rows()).to_have_count(2)
        expect(retract_page.version_row(2)).to_contain_text("latest")
        screenshot(admin_page, "retract-subset-latest-after")


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
            "/admin/update-published-dataset/search",
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
            data=json.dumps(
                {
                    "container_uuid": "00000000-0000-0000-0000-000000000000",
                    "version_uuids": ["00000000-0000-0000-0000-000000000000"],
                    "confirm_doi": "10.0/x",
                    "expected_doi": "10.0/x",
                }
            ),
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
            data=json.dumps(
                {
                    "container_uuid": "00000000-0000-0000-0000-000000000000",
                    "version_uuids": ["00000000-0000-0000-0000-000000000000"],
                    "confirm_doi": "wrong",
                    "expected_doi": "right",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400
        assert response.json()["code"] == "ConfirmationMismatch"

    @staticmethod
    def _execute(admin_page: Page, **overrides):
        payload = {
            "container_uuid": MULTI_SEEDS["older"]["container"],
            "version_uuids": [MULTI_SEEDS["older"]["versions"][0]],
            "confirm_doi": "10.0/x",
            "expected_doi": "10.0/x",
        }
        payload.update(overrides)
        payload = {key: value for key, value in payload.items() if value is not None}
        return admin_page.request.fetch(
            "/admin/update-published-dataset/retract/execute",
            method="PUT",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    def test_execute_api_rejects_missing_version_uuids(self, admin_page: Page):
        response = self._execute(admin_page, version_uuids=None)
        assert response.status == 400
        assert response.json()["code"] == "MissingRequiredField"

    def test_execute_api_rejects_empty_version_selection(self, admin_page: Page):
        response = self._execute(admin_page, version_uuids=[])
        assert response.status == 400
        assert response.json()["code"] == "MissingRequiredField"

    def test_execute_api_rejects_invalid_version_uuid(self, admin_page: Page):
        response = self._execute(admin_page, version_uuids=["not-a-uuid"])
        assert response.status == 400
        assert response.json()["code"] == "InvalidUuid"

    def test_execute_api_rejects_unknown_version(self, admin_page: Page):
        response = self._execute(admin_page, version_uuids=["99999999-9999-4999-8999-999999999999"])
        assert response.status == 400
        assert response.json()["code"] == "UnknownVersion"

    def test_execute_api_rejects_wrong_method(self, admin_page: Page):
        response = admin_page.request.post(
            "/admin/update-published-dataset/retract/execute",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 405
