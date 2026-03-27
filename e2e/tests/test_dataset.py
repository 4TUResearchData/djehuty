"""
Dataset CRUD tests.

Covers:
    - Create a new draft dataset
    - View and edit dataset metadata
    - Delete a draft dataset
    - Verify 404 for non-existent datasets
    - Verify 403 for unauthorized access to dataset editor

Run with:
    cd e2e && python -m pytest tests/test_dataset.py -v
"""

import re
import uuid

import pytest
from playwright.sync_api import Page, expect

from config import BASE_URL
from helpers.accounts import get_non_admin_account_uuid
from helpers.dataset import create_draft_dataset, get_container_uuid_from_url
from helpers.impersonation import impersonate, stop_impersonation
from pages.dataset_editor_page import DatasetEditorPage


@pytest.mark.dataset
class TestCreateDataset:
    """Test creating new draft datasets."""

    def test_create_new_dataset(self, authenticated_page: Page, screenshot):
        """Creating a new dataset should redirect to the editor."""
        authenticated_page.goto("/my/datasets")
        screenshot(authenticated_page, "my-datasets-before-create")

        authenticated_page.goto("/my/datasets/new")
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        screenshot(authenticated_page, "new-dataset-editor")

        editor = DatasetEditorPage(authenticated_page)
        assert editor.heading == "Add new dataset"
        expect(authenticated_page).to_have_url(
            re.compile(rf"{BASE_URL}/my/datasets/.+/edit")
        )

        # Clean up: delete the created dataset
        editor.delete()

    def test_new_dataset_has_empty_title(self, authenticated_page: Page, screenshot):
        """A new dataset should have a placeholder title, not a filled value."""
        url = create_draft_dataset(authenticated_page)
        screenshot(authenticated_page, "new-dataset-title")

        editor = DatasetEditorPage(authenticated_page)
        title_value = editor.get_title()
        # The title input should be empty (placeholder "Untitled item")
        assert title_value == ""

        # Clean up
        editor.delete()

    def test_new_dataset_appears_in_drafts_list(self, authenticated_page: Page, screenshot):
        """A newly created dataset should appear in the drafts list."""
        url = create_draft_dataset(authenticated_page)
        screenshot(authenticated_page, "new-dataset-created")

        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "drafts-list-with-new-dataset")

        # The drafts table should contain "Untitled item"
        drafts_table = authenticated_page.locator("#table-unpublished")
        expect(drafts_table).to_contain_text("Untitled item")

        # Clean up: go back and delete
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()


@pytest.mark.dataset
class TestEditDataset:
    """Test editing dataset metadata fields."""

    def test_edit_title_and_save(self, authenticated_page: Page, screenshot):
        """Editing the title and saving should persist the change."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        screenshot(authenticated_page, "before-edit-title")

        editor.set_title("E2E Test Dataset Title")
        editor.save()
        screenshot(authenticated_page, "after-save-title")

        # Reload the page to verify persistence
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "reloaded-after-save")

        assert editor.get_title() == "E2E Test Dataset Title"

        # Clean up
        editor.delete()

    def test_edit_description_and_save(self, authenticated_page: Page, screenshot):
        """Editing the description and saving should persist the change."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)

        editor.set_description("This is a test description for E2E.")
        editor.save()
        screenshot(authenticated_page, "after-save-description")

        # Reload to verify persistence
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "reloaded-description")

        description = editor.get_description_text()
        assert "This is a test description for E2E." in description

        # Clean up
        editor.delete()

    def test_edit_title_reflected_in_drafts_list(self, authenticated_page: Page, screenshot):
        """A saved title should appear in the drafts list on /my/datasets."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)

        test_title = f"Dataset CRUD Test {uuid.uuid4().hex[:8]}"
        editor.set_title(test_title)
        editor.save()

        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "drafts-list-with-updated-title")

        drafts_table = authenticated_page.locator("#table-unpublished")
        expect(drafts_table).to_contain_text(test_title)

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()

    def test_editor_has_save_and_delete_buttons(self, authenticated_page: Page, screenshot):
        """The dataset editor should show Save and Delete buttons for drafts."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        screenshot(authenticated_page, "editor-buttons")

        assert editor.is_save_visible()
        assert editor.is_delete_visible()
        assert editor.is_submit_visible()

        # Clean up
        editor.delete()


@pytest.mark.dataset
class TestDeleteDataset:
    """Test deleting draft datasets."""

    def test_delete_draft_dataset(self, authenticated_page: Page, screenshot):
        """Deleting a draft dataset should redirect to /my/datasets."""
        url = create_draft_dataset(authenticated_page)
        screenshot(authenticated_page, "before-delete")

        editor = DatasetEditorPage(authenticated_page)
        editor.delete()

        screenshot(authenticated_page, "after-delete")
        expect(authenticated_page).to_have_url(f"{BASE_URL}/my/datasets")

    def test_deleted_dataset_removed_from_drafts_list(self, authenticated_page: Page, screenshot):
        """A deleted dataset should no longer appear in the drafts list."""
        url = create_draft_dataset(authenticated_page)

        # Set a unique title so we can verify it's gone
        editor = DatasetEditorPage(authenticated_page)
        unique_title = f"DeleteMe-{uuid.uuid4().hex[:8]}"
        editor.set_title(unique_title)
        editor.save()

        # Verify it appears in the list first
        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        drafts_table = authenticated_page.locator("#table-unpublished")
        expect(drafts_table).to_contain_text(unique_title)
        screenshot(authenticated_page, "before-delete-in-list")

        # Now delete it
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()

        # Verify it's gone from the list
        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "after-delete-from-list")

        # The unique title should not appear anymore
        expect(authenticated_page.locator("body")).not_to_contain_text(unique_title)


@pytest.mark.dataset
class TestDatasetAccessControl:
    """Test access control for dataset pages."""

    def test_dataset_editor_requires_auth(self, page: Page, screenshot):
        """GET /my/datasets/<uuid>/edit without a session should return 403."""
        fake_uuid = str(uuid.uuid4())
        response = page.goto(f"/my/datasets/{fake_uuid}/edit")
        assert response is not None
        screenshot(page, "editor-403")
        assert response.status == 403

    def test_nonexistent_dataset_returns_404(self, page: Page, screenshot):
        """GET /datasets/<fake-uuid> should return 404."""
        fake_uuid = str(uuid.uuid4())
        response = page.goto(f"/datasets/{fake_uuid}")
        assert response is not None
        screenshot(page, "dataset-404")
        assert response.status == 404

    def test_other_users_dataset_not_accessible(self, admin_page: Page, screenshot):
        """A user should not be able to edit another user's draft dataset."""
        # Create a dataset as admin
        url = create_draft_dataset(admin_page)
        container_uuid = get_container_uuid_from_url(url)
        screenshot(admin_page, "admin-created-dataset")

        # Impersonate a non-admin user
        non_admin_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, non_admin_uuid)
        screenshot(admin_page, "impersonated-non-admin")

        # Try to access the admin's dataset editor
        response = admin_page.goto(f"/my/datasets/{container_uuid}/edit")
        assert response is not None
        screenshot(admin_page, "other-users-dataset-denied")
        assert response.status == 403

        # Stop impersonation and clean up
        stop_impersonation(admin_page)
        admin_page.goto(url)
        admin_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(admin_page).delete()

    def test_my_datasets_page_requires_auth(self, page: Page, screenshot):
        """GET /my/datasets without a session should return 403."""
        response = page.goto("/my/datasets")
        assert response is not None
        screenshot(page, "my-datasets-403")
        assert response.status == 403


@pytest.mark.dataset
class TestViewDataset:
    """Test viewing datasets (public dataset view page)."""

    def test_draft_dataset_not_publicly_visible(self, authenticated_page: Page, screenshot):
        """A draft dataset should not be viewable at /datasets/<uuid>."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)

        # Try to view it on the public page — unpublished datasets return
        # 404 (not found) or 410 (gone) depending on internal state.
        response = authenticated_page.goto(f"/datasets/{container_uuid}")
        assert response is not None
        screenshot(authenticated_page, "draft-not-public")
        assert response.status in (404, 410)

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()
