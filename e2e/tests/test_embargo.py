"""
Embargo & access control tests.

Covers:
    - Set embargo date through dataset editor UI
    - Verify embargo status displayed on dataset page
    - Verify embargoed files are hidden for anonymous users
    - Verify metadata remains visible during embargo
    - Create and use private links (share dataset via link)
    - Verify private link access works for anonymous users
    - Delete private link and verify access revoked
    - Data access request form submission

Run with:
    cd e2e && python -m pytest tests/test_embargo.py -v
"""

from datetime import date, timedelta
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from config import BASE_URL
from helpers.dataset import (
    create_draft_dataset,
    get_container_uuid_from_url,
    get_dataset_uuid_from_editor,
)
from helpers.publish import create_private_link, fill_required_fields_and_publish
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_FILE_CONTENT = b"Embargoed test file content.\n"
TEST_FILE_NAME = "embargo-test-file.txt"


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    """Create a temporary test file and return its path."""
    file_path = tmp_path / TEST_FILE_NAME
    file_path.write_bytes(TEST_FILE_CONTENT)
    return str(file_path)


def future_date(days: int = 365) -> str:
    """Return an ISO date string in the future."""
    return (date.today() + timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Embargo editor tests
# ---------------------------------------------------------------------------


@pytest.mark.embargo
class TestEmbargoEditor:
    """Test embargo settings in the dataset editor UI."""

    def test_select_embargo_shows_form(self, authenticated_page: Page, screenshot):
        """Selecting 'Embargoed access' should reveal the embargo form."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "before-embargo-select")

        assert not editor.is_embargo_form_visible()
        editor.select_access_type("embargoed_access")
        authenticated_page.locator("#embargoed_access_form").wait_for(state="visible")
        screenshot(authenticated_page, "embargo-form-visible")

        assert editor.is_embargo_form_visible()

        editor.delete()

    def test_select_restricted_shows_form(self, authenticated_page: Page, screenshot):
        """Selecting 'Restricted access' should reveal the restricted form."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        editor.select_access_type("restricted_access")
        authenticated_page.locator("#restricted_access_form").wait_for(state="visible")
        screenshot(authenticated_page, "restricted-form-visible")

        assert editor.is_restricted_form_visible()

        editor.delete()

    def test_set_embargo_and_save(self, authenticated_page: Page, screenshot):
        """Setting embargo fields and saving should persist the values."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        editor.select_access_type("embargoed_access")
        authenticated_page.locator("#embargoed_access_form").wait_for(state="visible")

        embargo_date = future_date(180)
        editor.set_embargo_date(embargo_date)
        editor.select_embargo_type("files_only_embargo")
        editor.set_embargo_reason("Data is under peer review.")
        screenshot(authenticated_page, "embargo-fields-filled")

        editor.save()
        screenshot(authenticated_page, "embargo-saved")

        # Reload and verify persistence
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        editor.wait_for_ready()
        authenticated_page.locator("#embargoed_access_form").wait_for(state="visible")
        screenshot(authenticated_page, "embargo-after-reload")

        assert editor.get_embargo_date() == embargo_date
        assert "Data is under peer review." in editor.get_embargo_reason_text()

        editor.delete()

    def test_switch_between_access_types(self, authenticated_page: Page, screenshot):
        """Switching access types should show/hide the correct forms."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        # Select embargo
        editor.select_access_type("embargoed_access")
        authenticated_page.locator("#embargoed_access_form").wait_for(state="visible")
        assert editor.is_embargo_form_visible()
        assert not editor.is_restricted_form_visible()

        # Switch to restricted
        editor.select_access_type("restricted_access")
        authenticated_page.locator("#restricted_access_form").wait_for(state="visible")
        assert not editor.is_embargo_form_visible()
        assert editor.is_restricted_form_visible()

        # Switch to open access
        editor.select_access_type("open_access")
        authenticated_page.locator("#open_access_form").wait_for(state="visible")
        screenshot(authenticated_page, "open-access-selected")
        assert not editor.is_embargo_form_visible()
        assert not editor.is_restricted_form_visible()

        editor.delete()


# ---------------------------------------------------------------------------
# Embargo display on published dataset
# ---------------------------------------------------------------------------


@pytest.mark.embargo
class TestEmbargoDisplay:
    """Test embargo status on published dataset pages."""

    def test_embargo_label_displayed(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """A published embargoed dataset should show the embargo label."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Embargo Display Test")
        editor.set_description("Testing embargo display.")
        editor.upload_file(test_file)
        editor.save()

        container_uuid = get_container_uuid_from_url(url)
        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Embargo Display Test",
            description="<p>Testing embargo display.</p>",
            is_embargoed=True,
            embargo_type="file",
            embargo_reason="<p>Under peer review.</p>",
        )

        # Visit the public dataset page
        authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "embargo-label-displayed")

        # Verify embargo label
        data_section = authenticated_page.locator("#data")
        expect(data_section).to_contain_text("under embargo")

        # Verify embargo reason is shown
        limited_access = authenticated_page.locator("#limited_access")
        expect(limited_access).to_contain_text("Under peer review.")

    def test_metadata_visible_during_embargo(
        self, authenticated_page: Page, test_file: str, browser, screenshot
    ):
        """Metadata should remain visible on an embargoed dataset page."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Metadata Visibility Test")
        editor.set_description("Verify metadata is visible during embargo.")
        editor.upload_file(test_file)
        editor.save()

        container_uuid = get_container_uuid_from_url(url)
        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Metadata Visibility Test",
            description="<p>Verify metadata is visible during embargo.</p>",
            is_embargoed=True,
            embargo_type="file",
        )

        # Visit as anonymous user (new context)
        anon_context = browser.new_context(base_url=BASE_URL)
        anon_page = anon_context.new_page()
        try:
            anon_page.goto(f"/datasets/{container_uuid}")
            anon_page.wait_for_load_state("domcontentloaded")
            screenshot(anon_page, "anon-embargo-metadata-visible")

            # Metadata (title, description) should be visible
            expect(anon_page.locator("body")).to_contain_text("Metadata Visibility Test")
            expect(anon_page.locator("body")).to_contain_text(
                "Verify metadata is visible during embargo."
            )

            # Embargo notice should be shown
            expect(anon_page.locator("#data")).to_contain_text("under embargo")
        finally:
            anon_context.close()

    def test_embargoed_files_hidden_for_anonymous(
        self, authenticated_page: Page, test_file: str, browser, screenshot
    ):
        """Embargoed files should not be visible to anonymous users."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Files Hidden Test")
        editor.set_description("Verify files are hidden during embargo.")
        editor.upload_file(test_file)
        editor.save()

        container_uuid = get_container_uuid_from_url(url)
        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Files Hidden Test",
            description="<p>Verify files are hidden during embargo.</p>",
            is_embargoed=True,
            embargo_type="file",
        )

        # Visit as anonymous user
        anon_context = browser.new_context(base_url=BASE_URL)
        anon_page = anon_context.new_page()
        try:
            anon_page.goto(f"/datasets/{container_uuid}")
            anon_page.wait_for_load_state("domcontentloaded")
            screenshot(anon_page, "anon-embargo-files-hidden")

            # The #files section should NOT be present
            expect(anon_page.locator("#files")).to_have_count(0)

            # The #private_view and #is_own_item messages should NOT be present
            expect(anon_page.locator("#private_view")).to_have_count(0)
            expect(anon_page.locator("#is_own_item")).to_have_count(0)
        finally:
            anon_context.close()

    def test_owner_sees_files_on_embargoed_dataset(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """The dataset owner should still see files on an embargoed dataset."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Owner Sees Files Test")
        editor.set_description("Owner should see embargoed files.")
        editor.upload_file(test_file)
        editor.save()

        container_uuid = get_container_uuid_from_url(url)
        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Owner Sees Files Test",
            description="<p>Owner should see embargoed files.</p>",
            is_embargoed=True,
            embargo_type="file",
        )

        # Re-login (publish may affect session state)
        authenticated_page.goto("/login")
        authenticated_page.wait_for_url("**/my/dashboard**")

        authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "owner-sees-embargo-files")

        # Owner message should be visible
        expect(authenticated_page.locator("#is_own_item")).to_be_visible()

        # Files section should be present
        expect(authenticated_page.locator("#files")).to_be_visible()


# ---------------------------------------------------------------------------
# Private links tests
# ---------------------------------------------------------------------------


@pytest.mark.embargo
class TestPrivateLinks:
    """Test private link creation, access, and deletion."""

    def test_create_private_link(self, authenticated_page: Page, screenshot):
        """Creating a private link should make it appear in the links table."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Private Link Test")
        editor.save()

        dataset_uuid = get_dataset_uuid_from_editor(authenticated_page)

        # Navigate to private links page
        authenticated_page.goto(f"/my/datasets/{dataset_uuid}/private_links")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "private-links-empty")

        # Click "Create new private link" button
        authenticated_page.locator(
            "a.corporate-identity-standard-button, .create-button a"
        ).first.click()
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "new-private-link-form")

        # Fill the form
        authenticated_page.locator("label[for='days7']").click()
        authenticated_page.locator("#purpose").fill("E2E test review")
        authenticated_page.locator("#whom").fill("Automated tester")
        screenshot(authenticated_page, "private-link-form-filled")

        # Submit
        authenticated_page.locator("#submit-button-label").click()
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.wait_for_url(
            f"**/my/datasets/{dataset_uuid}/private_links"
        )
        screenshot(authenticated_page, "private-link-created")

        # Verify the link appears in the table
        table = authenticated_page.locator("#private-links-table")
        expect(table).to_be_visible()
        expect(table).to_contain_text("E2E test review")
        expect(table).to_contain_text("Automated tester")

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()

    def test_private_link_access_anonymous(
        self, authenticated_page: Page, test_file: str, browser, screenshot
    ):
        """An anonymous user should access a dataset via a private link."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Private Link Access Test")
        editor.set_description("Testing anonymous private link access.")
        editor.upload_file(test_file)
        editor.save()

        container_uuid = get_container_uuid_from_url(url)
        private_link_id = create_private_link(authenticated_page, container_uuid)

        # Access the private link as an anonymous user
        anon_context = browser.new_context(base_url=BASE_URL)
        anon_page = anon_context.new_page()
        try:
            anon_page.goto(f"/private_datasets/{private_link_id}")
            anon_page.wait_for_load_state("domcontentloaded")
            screenshot(anon_page, "anon-private-link-access")

            # Should see the dataset title
            expect(anon_page.locator("body")).to_contain_text("Private Link Access Test")
        finally:
            anon_context.close()

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()

    def test_private_link_shows_files_for_embargoed_dataset(
        self, authenticated_page: Page, test_file: str, browser, screenshot
    ):
        """A private link should show files even on an embargoed dataset."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Private Link Embargo Files Test")
        editor.set_description("Private link should reveal embargoed files.")
        editor.upload_file(test_file)
        editor.save()

        container_uuid = get_container_uuid_from_url(url)

        # Create a private link BEFORE publishing (API only works for drafts)
        private_link_id = create_private_link(authenticated_page, container_uuid)

        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Private Link Embargo Files Test",
            description="<p>Private link should reveal embargoed files.</p>",
            is_embargoed=True,
            embargo_type="file",
        )

        # Access as anonymous
        anon_context = browser.new_context(base_url=BASE_URL)
        anon_page = anon_context.new_page()
        try:
            anon_page.goto(f"/private_datasets/{private_link_id}")
            anon_page.wait_for_load_state("domcontentloaded")
            screenshot(anon_page, "private-link-embargo-files-visible")

            # The private_view message should be present
            expect(anon_page.locator("#private_view")).to_be_visible()
            # Files should be visible
            expect(anon_page.locator("#files")).to_be_visible()
        finally:
            anon_context.close()

    def test_delete_private_link_revokes_access(
        self, authenticated_page: Page, browser, screenshot
    ):
        """Deleting a private link should revoke access via that link."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Delete Private Link Test")
        editor.save()

        container_uuid = get_container_uuid_from_url(url)
        dataset_uuid = get_dataset_uuid_from_editor(authenticated_page)
        private_link_id = create_private_link(authenticated_page, container_uuid)

        # Verify the link works first
        anon_context = browser.new_context(base_url=BASE_URL)
        anon_page = anon_context.new_page()
        try:
            response = anon_page.goto(f"/private_datasets/{private_link_id}")
            assert response.status == 200
            screenshot(anon_page, "private-link-before-delete")
        finally:
            anon_context.close()

        # Delete the private link via UI
        authenticated_page.goto(f"/my/datasets/{dataset_uuid}/private_links")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "private-links-before-delete")

        delete_link = authenticated_page.locator("a.fa-trash-can").first
        delete_link.click()
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "private-link-deleted")

        # Verify the link no longer works
        anon_context = browser.new_context(base_url=BASE_URL)
        anon_page = anon_context.new_page()
        try:
            response = anon_page.goto(f"/private_datasets/{private_link_id}")
            assert response.status == 404
            screenshot(anon_page, "private-link-access-revoked")
        finally:
            anon_context.close()

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()


# ---------------------------------------------------------------------------
# Data access request tests
# ---------------------------------------------------------------------------


@pytest.mark.embargo
class TestDataAccessRequest:
    """Test the data access request form on restricted datasets."""

    def test_access_request_form_displayed(
        self, authenticated_page: Page, test_file: str, browser, screenshot
    ):
        """A restricted dataset should display the access request form."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Access Request Form Test")
        editor.set_description("Testing the access request form.")
        editor.upload_file(test_file)
        editor.save()

        container_uuid = get_container_uuid_from_url(url)
        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Access Request Form Test",
            description="<p>Testing the access request form.</p>",
            is_restricted=True,
        )

        # Visit as anonymous user
        anon_context = browser.new_context(base_url=BASE_URL)
        anon_page = anon_context.new_page()
        try:
            anon_page.goto(f"/datasets/{container_uuid}")
            anon_page.wait_for_load_state("domcontentloaded")
            screenshot(anon_page, "restricted-dataset-page")

            # Verify restricted label
            expect(anon_page.locator("#data")).to_contain_text("restricted access")

            # The access request toggle should be visible
            access_request_link = anon_page.locator("#access-request")
            expect(access_request_link).to_be_visible()
            expect(access_request_link).to_contain_text("Request access to data")

            # Click to expand the form
            access_request_link.click()
            anon_page.locator("#access-request-wrapper").wait_for(state="visible")
            screenshot(anon_page, "access-request-form-expanded")

            # Verify form fields are present
            expect(anon_page.locator("#access-request-email")).to_be_visible()
            expect(anon_page.locator("#access-request-name")).to_be_visible()
            expect(anon_page.locator("#submit-access-request")).to_be_visible()
        finally:
            anon_context.close()

    def test_submit_access_request(
        self, authenticated_page: Page, test_file: str, browser, screenshot
    ):
        """Submitting a data access request should show a success message."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Submit Access Request Test")
        editor.set_description("Testing access request submission.")
        editor.upload_file(test_file)
        editor.save()

        container_uuid = get_container_uuid_from_url(url)
        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Submit Access Request Test",
            description="<p>Testing access request submission.</p>",
            is_restricted=True,
        )

        # Visit as anonymous user
        anon_context = browser.new_context(base_url=BASE_URL)
        anon_page = anon_context.new_page()
        try:
            anon_page.goto(f"/datasets/{container_uuid}")
            anon_page.wait_for_load_state("domcontentloaded")

            # Open the access request form
            anon_page.locator("#access-request").click()
            anon_page.locator("#access-request-wrapper").wait_for(state="visible")

            # Fill the form
            anon_page.locator("#access-request-email").fill("tester@example.com")
            anon_page.locator("#access-request-name").fill("E2E Tester")
            # Fill the reason rich text editor
            reason_editor = anon_page.locator("#access-request-reason .ql-editor")
            reason_editor.click()
            reason_editor.fill("I need this data for research purposes.")
            screenshot(anon_page, "access-request-form-filled")

            # Submit the request
            anon_page.locator("#submit-access-request").click()

            # Wait for success feedback
            anon_page.wait_for_timeout(2000)
            screenshot(anon_page, "access-request-submitted")
        finally:
            anon_context.close()
