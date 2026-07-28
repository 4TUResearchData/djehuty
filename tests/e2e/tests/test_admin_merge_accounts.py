"""
Admin "merge accounts" tests.

Covers:
    - /admin/users/merge page rendering and admin-only access
    - "Merge accounts" entry link on /admin/users
    - JSON validation on /admin/users/merge/preview
    - JSON validation on /admin/users/merge/execute
    - Non-admin gets 403 on every merge endpoint
    - Full UI flow: source account creates a draft, admin merges,
      ownership is reassigned in the SPARQL store

Run with:
    cd tests/e2e && python -m pytest tests/test_admin_merge_accounts.py -v
"""

import pytest
import requests
from playwright.sync_api import Page, expect

from config import ADMIN_EMAIL, SPARQL_GRAPH, SPARQL_URL
from helpers.accounts import get_account_uuid, get_non_admin_account
from helpers.dataset import create_draft_dataset, get_container_uuid_from_url
from helpers.impersonation import impersonate, stop_impersonation
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Local SPARQL helper
# ---------------------------------------------------------------------------


def get_container_owner_uuid(container_uuid: str) -> str | None:
    """Return the ``djht:account`` UUID currently set on a container, or None."""
    query = f"""
        PREFIX djht: <https://ontologies.data.4tu.nl/djehuty/0.0.1/>
        SELECT ?owner WHERE {{
          GRAPH <{SPARQL_GRAPH}> {{
            <container:{container_uuid}> djht:account ?account .
          }}
          BIND(STRAFTER(STR(?account), "account:") AS ?owner)
        }} LIMIT 1
    """
    response = requests.get(
        SPARQL_URL,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=15,
    )
    response.raise_for_status()
    bindings = response.json()["results"]["bindings"]
    return bindings[0]["owner"]["value"] if bindings else None


# ---------------------------------------------------------------------------
# Page-level / access control
# ---------------------------------------------------------------------------


@pytest.mark.admin
@pytest.mark.admin_merge_accounts
class TestAdminMergeAccountsPage:
    """Verify the merge-accounts page renders and is admin-gated."""

    def test_merge_page_accessible(self, admin_page: Page, screenshot):
        """Admin can load /admin/users/merge and sees the form."""
        response = admin_page.goto("/admin/users/merge")
        assert response is not None
        assert response.status == 200
        screenshot(admin_page, "merge-page")

        expect(admin_page.locator("body")).to_contain_text("Merge accounts")
        expect(admin_page.locator("#from-email")).to_be_visible()
        expect(admin_page.locator("#to-email")).to_be_visible()
        expect(admin_page.locator("#merge-preview-button")).to_be_visible()
        expect(admin_page.locator("#merge-preview")).to_be_hidden()

    def test_users_page_has_merge_button(self, admin_page: Page, screenshot):
        """The /admin/users page links to the merge page."""
        admin_page.goto("/admin/users")
        admin_page.wait_for_load_state("domcontentloaded")
        screenshot(admin_page, "users-page-with-merge-button")

        merge_link = admin_page.locator("a[href='/admin/users/merge']")
        expect(merge_link).to_be_visible()
        expect(merge_link).to_contain_text("Merge accounts")

    def test_non_admin_gets_403_on_merge_page(self, admin_page: Page, screenshot):
        """A non-admin user receives 403 on /admin/users/merge."""
        non_admin_uuid = get_non_admin_account()["uuid"]
        impersonate(admin_page, non_admin_uuid)

        response = admin_page.goto("/admin/users/merge")
        assert response is not None
        screenshot(admin_page, "non-admin-merge-403")
        assert response.status == 403

        stop_impersonation(admin_page)


# ---------------------------------------------------------------------------
# JSON API validation
# ---------------------------------------------------------------------------


@pytest.mark.admin
@pytest.mark.admin_merge_accounts
class TestAdminMergeAccountsApi:
    """Verify validation on /admin/users/merge/{preview,execute}."""

    def _post_json(self, admin_page: Page, path: str, body: dict):
        return admin_page.request.post(
            path,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    def test_preview_rejects_get(self, admin_page: Page):
        """GET on the preview endpoint should not be allowed."""
        response = admin_page.request.get("/admin/users/merge/preview")
        assert response.status == 405

    def test_preview_requires_emails(self, admin_page: Page):
        """An empty body should produce a 400 about the missing source email."""
        response = self._post_json(admin_page, "/admin/users/merge/preview", {})
        assert response.status == 400
        body = response.json()
        assert "E-mail address is required" in body["message"]

    def test_preview_unknown_source_email(self, admin_page: Page):
        """Preview returns 400 when the source email isn't an account."""
        response = self._post_json(
            admin_page,
            "/admin/users/merge/preview",
            {
                "from_email": "no-such-account@example.org",
                "to_email":   ADMIN_EMAIL,
            },
        )
        assert response.status == 400
        body = response.json()
        assert "No account found" in body["message"]
        assert "Source account" in body["message"]

    def test_preview_unknown_target_email(self, admin_page: Page):
        """Preview returns 400 when the target email isn't an account."""
        response = self._post_json(
            admin_page,
            "/admin/users/merge/preview",
            {
                "from_email": ADMIN_EMAIL,
                "to_email":   "no-such-account@example.org",
            },
        )
        assert response.status == 400
        assert "Target account" in response.json()["message"]

    def test_preview_same_account(self, admin_page: Page):
        """Preview returns 400 when source and target are the same account."""
        response = self._post_json(
            admin_page,
            "/admin/users/merge/preview",
            {"from_email": ADMIN_EMAIL, "to_email": ADMIN_EMAIL},
        )
        assert response.status == 400
        assert "same" in response.json()["message"].lower()

    def test_execute_rejects_get(self, admin_page: Page):
        """GET on the execute endpoint should not be allowed."""
        response = admin_page.request.get("/admin/users/merge/execute")
        assert response.status == 405

    def test_execute_invalid_uuid(self, admin_page: Page):
        """Execute returns 400 when a UUID is malformed."""
        response = self._post_json(
            admin_page,
            "/admin/users/merge/execute",
            {"from_account_uuid": "not-a-uuid", "to_account_uuid": "also-not"},
        )
        assert response.status == 400
        assert "Invalid source account UUID" in response.json()["message"]

    def test_execute_same_uuid(self, admin_page: Page):
        """Execute returns 400 when source and target UUIDs are equal."""
        admin_uuid = get_account_uuid(ADMIN_EMAIL)
        assert admin_uuid is not None
        response = self._post_json(
            admin_page,
            "/admin/users/merge/execute",
            {"from_account_uuid": admin_uuid, "to_account_uuid": admin_uuid},
        )
        assert response.status == 400
        assert "same" in response.json()["message"].lower()

    def test_non_admin_preview_403(self, admin_page: Page):
        """A non-admin POSTing to preview is denied."""
        non_admin_uuid = get_non_admin_account()["uuid"]
        impersonate(admin_page, non_admin_uuid)
        try:
            response = self._post_json(
                admin_page,
                "/admin/users/merge/preview",
                {"from_email": ADMIN_EMAIL, "to_email": "x@example.org"},
            )
            assert response.status == 403
        finally:
            stop_impersonation(admin_page)

    def test_non_admin_execute_403(self, admin_page: Page):
        """A non-admin POSTing to execute is denied."""
        non_admin_uuid = get_non_admin_account()["uuid"]
        impersonate(admin_page, non_admin_uuid)
        try:
            response = self._post_json(
                admin_page,
                "/admin/users/merge/execute",
                {
                    "from_account_uuid": non_admin_uuid,
                    "to_account_uuid":   non_admin_uuid,
                },
            )
            assert response.status == 403
        finally:
            stop_impersonation(admin_page)


# ---------------------------------------------------------------------------
# End-to-end merge flow
# ---------------------------------------------------------------------------


@pytest.mark.admin
@pytest.mark.admin_merge_accounts
class TestAdminMergeAccountsFlow:
    """Run the full preview-and-execute flow and verify SPARQL state."""

    def _create_draft_as(self, page: Page, account_uuid: str) -> str:
        """Impersonate ACCOUNT_UUID, create a draft, return its container UUID."""
        impersonate(page, account_uuid)
        try:
            url = create_draft_dataset(page)
            container_uuid = get_container_uuid_from_url(url)
        finally:
            stop_impersonation(page)
        return container_uuid

    def test_preview_lists_source_containers(
        self, admin_page: Page, screenshot
    ):
        """Preview must return the source account's containers."""
        non_admin = get_non_admin_account()
        admin_uuid = get_account_uuid(ADMIN_EMAIL)
        assert admin_uuid is not None

        container_uuid = self._create_draft_as(admin_page, non_admin["uuid"])

        admin_page.goto("/admin/users/merge")
        admin_page.locator("#from-email").fill(non_admin["email"])
        admin_page.locator("#to-email").fill(ADMIN_EMAIL)
        screenshot(admin_page, "merge-form-filled")

        admin_page.locator("#merge-preview-button").click()
        admin_page.locator("#merge-preview").wait_for(state="visible")
        screenshot(admin_page, "merge-preview-shown")

        table = admin_page.locator("#merge-containers-table")
        expect(table).to_contain_text(container_uuid)
        count_text = admin_page.locator("#preview-count").inner_text()
        assert int(count_text) >= 1

        # The merge confirm button should be enabled (no longer .disabled)
        confirm_button = admin_page.locator("#merge-confirm-button")
        expect(confirm_button).not_to_have_class("disabled")

        # Clean up: admin merges into self so it can be deleted in next test path.
        # Here we leave the container with the non-admin and delete it directly
        # by re-impersonating.
        impersonate(admin_page, non_admin["uuid"])
        try:
            admin_page.goto(f"/my/datasets/{container_uuid}/edit")
            admin_page.wait_for_load_state("domcontentloaded")
            DatasetEditorPage(admin_page).delete()
        finally:
            stop_impersonation(admin_page)

    def test_execute_reassigns_container_ownership(
        self, admin_page: Page, screenshot
    ):
        """After confirming the merge, the container's djht:account changes."""
        non_admin = get_non_admin_account()
        admin_uuid = get_account_uuid(ADMIN_EMAIL)
        assert admin_uuid is not None

        container_uuid = self._create_draft_as(admin_page, non_admin["uuid"])

        # Sanity: container starts owned by the source (non-admin) account.
        assert get_container_owner_uuid(container_uuid) == non_admin["uuid"]

        admin_page.goto("/admin/users/merge")
        admin_page.locator("#from-email").fill(non_admin["email"])
        admin_page.locator("#to-email").fill(ADMIN_EMAIL)
        admin_page.locator("#merge-preview-button").click()
        admin_page.locator("#merge-preview").wait_for(state="visible")
        screenshot(admin_page, "merge-before-confirm")

        # Accept the JavaScript confirm() dialog the page raises.
        admin_page.once("dialog", lambda dialog: dialog.accept())
        admin_page.locator("#merge-confirm-button").click()

        # Wait for the success message bar to appear and the preview to hide.
        admin_page.locator("#message.success").wait_for(state="visible")
        admin_page.locator("#merge-preview").wait_for(state="hidden")
        screenshot(admin_page, "merge-after-confirm")

        # The container is now owned by the target (admin) account.
        assert get_container_owner_uuid(container_uuid) == admin_uuid

        # Form inputs are cleared on success.
        assert admin_page.locator("#from-email").input_value() == ""
        assert admin_page.locator("#to-email").input_value() == ""

        # Clean up: admin owns the container now, so it can delete it directly.
        admin_page.goto(f"/my/datasets/{container_uuid}/edit")
        admin_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(admin_page).delete()
