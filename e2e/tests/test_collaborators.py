"""
Collaborator management tests.

Covers:
    - Add collaborator through UI (autocomplete search and selection)
    - Remove collaborator
    - Verify collaborator list display
    - Verify permission-based access (can/cannot edit based on role)

Run with:
    cd e2e && python -m pytest tests/test_collaborators.py -v
"""

import pytest
from playwright.sync_api import Page, expect

from helpers.accounts import get_non_admin_account, get_non_admin_account_uuid
from helpers.dataset import (
    create_draft_dataset,
    get_container_uuid_from_url,
)
from helpers.impersonation import impersonate, stop_impersonation
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def expand_collaborators(page: Page):
    """Click 'Manage collaborators' and wait for the table to appear."""
    page.locator("#expand-collaborators-button").click()
    page.locator("#expanded-collaborators").wait_for(state="visible")
    # Wait for the collaborators AJAX to render (add-row input appears)
    page.locator("#add_collaborator").wait_for(state="visible")


def add_collaborator_via_ui(page: Page, email: str, permissions: dict | None = None):
    """Search for an account by email, select it from autocomplete, and add it.

    Args:
        page: The dataset editor page with collaborators expanded.
        email: Email address to search for (unique identifier).
        permissions: Optional dict with keys 'metadata_edit', 'data_read',
                     'data_edit', 'data_remove'. Values are bools.
    """
    input_field = page.locator("#add_collaborator")
    input_field.fill(email)

    # Wait for autocomplete results
    page.locator("#collaborator-ac").wait_for(state="visible")
    # Click the first (and only) result matching this email
    page.locator("#collaborator-ac ul li a").first.click()
    # After selection, the hidden account_uuid field should be filled
    expect(page.locator("#account_uuid")).not_to_have_value("")

    # Set optional permissions via checkboxes in the add-row (first tbody row)
    add_row = page.locator("#collaborators-form tbody tr").first
    if permissions:
        if permissions.get("metadata_edit"):
            add_row.locator("input.subitem-checkbox-metadata[name='edit']").check()
        if permissions.get("data_read"):
            add_row.locator("input.subitem-checkbox-data[name='read']").check()
        if permissions.get("data_edit"):
            add_row.locator("input.subitem-checkbox-data[name='edit']").check()
        if permissions.get("data_remove"):
            add_row.locator("input.subitem-checkbox-data[name='remove']").check()

    # Click the add button
    page.locator("#add-collaborator-button").click()
    # Wait for the list to re-render: a collaborator row with an id starting
    # with "row-" should appear (the add-row does not have such an id).
    # Use a longer timeout because the AJAX call can be slow in CI.
    page.locator("#collaborators-form tbody tr[id^='row-']").first.wait_for(
        state="visible", timeout=60000
    )


def get_collaborator_rows(page: Page):
    """Return locator for collaborator data rows (those with a row-<uuid> id)."""
    return page.locator("#collaborators-form tbody tr[id^='row-']")


# ---------------------------------------------------------------------------
# Add collaborator tests
# ---------------------------------------------------------------------------


@pytest.mark.collaborators
class TestAddCollaborator:
    """Test adding collaborators through the dataset editor UI."""

    def test_add_collaborator_via_autocomplete(self, authenticated_page: Page, screenshot):
        """Searching for a user and selecting them should add a collaborator row."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "editor-before-collaborators")

        # Get a non-admin account to add as collaborator
        account = get_non_admin_account("?uuid ?email")

        expand_collaborators(authenticated_page)
        screenshot(authenticated_page, "collaborators-expanded")

        # Verify table starts empty (no collaborator rows)
        assert get_collaborator_rows(authenticated_page).count() == 0

        add_collaborator_via_ui(authenticated_page, account["email"])
        screenshot(authenticated_page, "collaborator-added")

        # Verify the collaborator appears in the list
        rows = get_collaborator_rows(authenticated_page)
        assert rows.count() == 1
        row_text = rows.first.inner_text()
        assert account["email"] in row_text

        # Clean up
        editor.delete()

    def test_add_collaborator_with_permissions(self, authenticated_page: Page, screenshot):
        """Adding a collaborator with specific permissions should persist them."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        account = get_non_admin_account("?uuid ?email")

        expand_collaborators(authenticated_page)
        add_collaborator_via_ui(authenticated_page, account["email"], permissions={
            "metadata_edit": True,
            "data_read": True,
            "data_edit": True,
        })
        screenshot(authenticated_page, "collaborator-with-permissions")

        # Verify the collaborator row has the expected checkboxes checked
        row = get_collaborator_rows(authenticated_page).first
        expect(row.locator("input.subitem-checkbox-metadata[name='read']")).to_be_checked()
        expect(row.locator("input.subitem-checkbox-metadata[name='edit']")).to_be_checked()
        expect(row.locator("input.subitem-checkbox-data[name='read']")).to_be_checked()
        expect(row.locator("input.subitem-checkbox-data[name='edit']")).to_be_checked()
        expect(row.locator("input.subitem-checkbox-data[name='remove']")).not_to_be_checked()

        # Clean up
        editor.delete()

    def test_autocomplete_requires_three_chars(self, authenticated_page: Page, screenshot):
        """Typing fewer than 3 characters should not trigger autocomplete."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        expand_collaborators(authenticated_page)

        # Type only 2 characters
        authenticated_page.locator("#add_collaborator").fill("ab")
        # Short wait to confirm no autocomplete appears
        authenticated_page.wait_for_timeout(500)
        assert not authenticated_page.locator("#collaborator-ac").is_visible()
        screenshot(authenticated_page, "no-autocomplete-for-short-input")

        # Clean up
        editor.delete()


# ---------------------------------------------------------------------------
# Remove collaborator tests
# ---------------------------------------------------------------------------


@pytest.mark.collaborators
class TestRemoveCollaborator:
    """Test removing collaborators from a dataset."""

    def test_remove_collaborator(self, authenticated_page: Page, screenshot):
        """Clicking the trash icon should remove the collaborator from the list."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        account = get_non_admin_account("?uuid ?email")

        expand_collaborators(authenticated_page)
        add_collaborator_via_ui(authenticated_page, account["email"])
        screenshot(authenticated_page, "before-remove")

        assert get_collaborator_rows(authenticated_page).count() == 1

        # Click the remove (trash) button on the collaborator row
        row = get_collaborator_rows(authenticated_page).first
        row.locator("a.fa-trash-can").click()
        # Wait for the collaborator row to disappear after AJAX re-render
        page = authenticated_page
        page.locator("#collaborators-form tbody tr[id^='row-']").wait_for(
            state="hidden", timeout=10000
        )
        screenshot(authenticated_page, "after-remove")

        assert get_collaborator_rows(authenticated_page).count() == 0

        # Clean up
        editor.delete()


# ---------------------------------------------------------------------------
# Collaborator list display tests
# ---------------------------------------------------------------------------


@pytest.mark.collaborators
class TestCollaboratorDisplay:
    """Test the collaborator list display in the dataset editor."""

    def test_collaborators_section_toggle(self, authenticated_page: Page, screenshot):
        """Clicking 'Manage collaborators' should show/hide the table."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "before-expand")

        # Verify initially hidden
        assert not authenticated_page.locator("#expanded-collaborators").is_visible()

        # Expand
        authenticated_page.locator("#expand-collaborators-button").click()
        authenticated_page.locator("#expanded-collaborators").wait_for(state="visible")
        screenshot(authenticated_page, "expanded")

        button_text = authenticated_page.locator("#expand-collaborators-button").inner_text()
        assert "Hide" in button_text

        # Collapse
        authenticated_page.locator("#expand-collaborators-button").click()
        authenticated_page.locator("#expanded-collaborators").wait_for(state="hidden")
        screenshot(authenticated_page, "collapsed")

        button_text = authenticated_page.locator("#expand-collaborators-button").inner_text()
        assert "Manage" in button_text

        # Clean up
        editor.delete()

    def test_collaborator_row_shows_email(self, authenticated_page: Page, screenshot):
        """Each collaborator row should display the user's email address."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        account = get_non_admin_account("?uuid ?email")

        expand_collaborators(authenticated_page)
        add_collaborator_via_ui(authenticated_page, account["email"])
        screenshot(authenticated_page, "collaborator-row-display")

        row = get_collaborator_rows(authenticated_page).first
        row_text = row.inner_text()
        assert account["email"] in row_text

        # Clean up
        editor.delete()

    def test_collaborator_has_permission_checkboxes(self, authenticated_page: Page, screenshot):
        """Each collaborator row should have 5 permission checkboxes."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        account = get_non_admin_account("?uuid ?email")

        expand_collaborators(authenticated_page)
        add_collaborator_via_ui(authenticated_page, account["email"])
        screenshot(authenticated_page, "permission-checkboxes")

        row = get_collaborator_rows(authenticated_page).first
        # 2 metadata checkboxes + 3 data checkboxes = 5 total
        checkboxes = row.locator("input[type='checkbox']")
        assert checkboxes.count() == 5

        # Clean up
        editor.delete()

    def test_metadata_read_always_checked_by_default(self, authenticated_page: Page, screenshot):
        """A newly added collaborator should always have metadata read checked."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        account = get_non_admin_account("?uuid ?email")

        expand_collaborators(authenticated_page)
        add_collaborator_via_ui(authenticated_page, account["email"])
        screenshot(authenticated_page, "default-permissions")

        row = get_collaborator_rows(authenticated_page).first
        expect(row.locator("input.subitem-checkbox-metadata[name='read']")).to_be_checked()

        # Clean up
        editor.delete()


# ---------------------------------------------------------------------------
# Permission-based access tests
# ---------------------------------------------------------------------------


@pytest.mark.collaborators
class TestCollaboratorAccess:
    """Test that collaborators can/cannot access datasets based on permissions."""

    def test_collaborator_can_access_shared_dataset(self, admin_page: Page, screenshot):
        """A collaborator with metadata_read should be able to access the dataset."""
        # Create a dataset as admin
        url = create_draft_dataset(admin_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(admin_page)
        editor.wait_for_ready()
        editor.set_title("Collaboration Test Dataset")
        editor.save()
        screenshot(admin_page, "admin-created-dataset")

        # Get a specific non-admin account and add them as collaborator
        non_admin = get_non_admin_account("?uuid ?email")

        expand_collaborators(admin_page)
        add_collaborator_via_ui(admin_page, non_admin["email"])
        screenshot(admin_page, "collaborator-added")

        # Impersonate that same user
        impersonate(admin_page, non_admin["uuid"])
        screenshot(admin_page, "impersonated-collaborator")

        # Access the shared dataset editor
        response = admin_page.goto(f"/my/datasets/{container_uuid}/edit")
        admin_page.wait_for_load_state("domcontentloaded")
        assert response is not None
        screenshot(admin_page, "collaborator-viewing-dataset")
        assert response.status == 200

        # Stop impersonation and clean up
        stop_impersonation(admin_page)
        admin_page.goto(url)
        admin_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(admin_page).delete()

    def test_non_collaborator_cannot_access_dataset(self, admin_page: Page, screenshot):
        """A user who is NOT a collaborator should get 403 on the dataset editor."""
        # Create a dataset as admin (no collaborators added)
        url = create_draft_dataset(admin_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(admin_page)
        editor.wait_for_ready()
        screenshot(admin_page, "admin-created-private-dataset")

        # Impersonate a non-admin user (not a collaborator)
        non_admin_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, non_admin_uuid)
        screenshot(admin_page, "impersonated-non-collaborator")

        # Try to access the dataset editor — should be denied
        response = admin_page.goto(f"/my/datasets/{container_uuid}/edit")
        assert response is not None
        screenshot(admin_page, "access-denied")
        assert response.status == 403

        # Stop impersonation and clean up
        stop_impersonation(admin_page)
        admin_page.goto(url)
        admin_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(admin_page).delete()

    def test_collaborator_with_edit_can_modify_metadata(self, admin_page: Page, screenshot):
        """A collaborator with metadata_edit should be able to save changes."""
        # Create dataset as admin
        url = create_draft_dataset(admin_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(admin_page)
        editor.wait_for_ready()
        editor.set_title("Editable Collaboration Dataset")
        editor.save()
        screenshot(admin_page, "admin-dataset-created")

        # Add collaborator with metadata edit permission
        non_admin = get_non_admin_account("?uuid ?email")

        expand_collaborators(admin_page)
        add_collaborator_via_ui(admin_page, non_admin["email"], permissions={
            "metadata_edit": True,
        })
        screenshot(admin_page, "collaborator-with-edit-added")

        # Impersonate the collaborator
        impersonate(admin_page, non_admin["uuid"])

        # Navigate to the shared dataset
        admin_page.goto(f"/my/datasets/{container_uuid}/edit")
        admin_page.wait_for_load_state("domcontentloaded")
        collab_editor = DatasetEditorPage(admin_page)
        collab_editor.wait_for_ready()
        screenshot(admin_page, "collaborator-editing")

        # The save button should be available
        assert collab_editor.is_save_visible()

        # Modify the title and save
        collab_editor.set_title("Modified by Collaborator")
        collab_editor.save()
        screenshot(admin_page, "collaborator-saved-changes")

        # Verify the title was saved
        assert collab_editor.get_title() == "Modified by Collaborator"

        # Stop impersonation and clean up
        stop_impersonation(admin_page)
        admin_page.goto(url)
        admin_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(admin_page).delete()

    def test_collaborator_without_edit_sees_readonly(self, admin_page: Page, screenshot):
        """A collaborator with only metadata_read should see a read-only view."""
        # Create dataset as admin
        url = create_draft_dataset(admin_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(admin_page)
        editor.wait_for_ready()
        editor.set_title("Read-Only Collaboration Dataset")
        editor.save()
        screenshot(admin_page, "admin-dataset-for-readonly")

        # Add collaborator with only read access (default: metadata_read only)
        non_admin = get_non_admin_account("?uuid ?email")

        expand_collaborators(admin_page)
        add_collaborator_via_ui(admin_page, non_admin["email"])
        screenshot(admin_page, "readonly-collaborator-added")

        # Impersonate the collaborator
        impersonate(admin_page, non_admin["uuid"])

        # Navigate to the shared dataset
        admin_page.goto(f"/my/datasets/{container_uuid}/edit")
        admin_page.wait_for_load_state("domcontentloaded")
        collab_editor = DatasetEditorPage(admin_page)
        collab_editor.wait_for_ready()
        screenshot(admin_page, "readonly-collaborator-view")

        # The collaborator label should say "Show collaborators" (not "Manage")
        button_text = admin_page.locator("#expand-collaborators-button").inner_text()
        assert "Show" in button_text
        screenshot(admin_page, "readonly-collaborator-final")

        # Stop impersonation and clean up
        stop_impersonation(admin_page)
        admin_page.goto(url)
        admin_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(admin_page).delete()

    def test_collaborator_cannot_manage_collaborators(self, admin_page: Page, screenshot):
        """A collaborator (even with edit) should not be able to add other collaborators."""
        # Create dataset as admin
        url = create_draft_dataset(admin_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(admin_page)
        editor.wait_for_ready()
        screenshot(admin_page, "admin-dataset")

        # Add collaborator with metadata edit
        non_admin = get_non_admin_account("?uuid ?email")

        expand_collaborators(admin_page)
        add_collaborator_via_ui(admin_page, non_admin["email"], permissions={
            "metadata_edit": True,
        })
        screenshot(admin_page, "collaborator-added-for-manage-test")

        # Impersonate the collaborator
        impersonate(admin_page, non_admin["uuid"])

        # Navigate to the shared dataset
        admin_page.goto(f"/my/datasets/{container_uuid}/edit")
        admin_page.wait_for_load_state("domcontentloaded")
        collab_editor = DatasetEditorPage(admin_page)
        collab_editor.wait_for_ready()

        # The "Show collaborators" button should show (not "Manage")
        button_text = admin_page.locator("#expand-collaborators-button").inner_text()
        screenshot(admin_page, "collaborator-cannot-manage")
        assert "Show" in button_text

        # Stop impersonation and clean up
        stop_impersonation(admin_page)
        admin_page.goto(url)
        admin_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(admin_page).delete()
