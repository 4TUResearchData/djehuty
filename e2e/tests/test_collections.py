"""
Collection management tests.

Covers:
    - Create a new collection through UI
    - View collection detail page
    - Edit collection metadata
    - Add/remove datasets from collection
    - Delete collection
    - Collection publish workflow

Run with:
    cd e2e && python -m pytest tests/test_collections.py -v
"""

import re
import uuid

import pytest
from playwright.sync_api import Page, expect

from config import BASE_URL
from helpers.accounts import get_non_admin_account_uuid
from helpers.collection import (
    create_draft_collection,
    fill_required_fields_and_publish_collection,
    get_container_uuid_from_url,
)
from helpers.dataset import create_draft_dataset
from helpers.dataset import get_container_uuid_from_url as get_dataset_uuid_from_url
from helpers.impersonation import impersonate, stop_impersonation
from helpers.publish import fill_required_fields_and_publish
from pages.collection_editor_page import CollectionEditorPage
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def published_dataset(authenticated_page: Page, tmp_path):
    """Create and publish a dataset, returning its container_uuid."""
    # Create a test file for the dataset
    file_path = tmp_path / "collection-test-file.txt"
    file_path.write_bytes(b"File for collection test.\n")

    url = create_draft_dataset(authenticated_page)
    container_uuid = get_dataset_uuid_from_url(url)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(str(file_path))
    editor.save()

    fill_required_fields_and_publish(
        authenticated_page,
        container_uuid,
        title="Dataset for Collection Test",
    )

    # Re-login after publish
    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")

    return container_uuid


# ---------------------------------------------------------------------------
# Create collection tests
# ---------------------------------------------------------------------------


@pytest.mark.collections
class TestCreateCollection:
    """Test creating new draft collections."""

    def test_create_new_collection(self, authenticated_page: Page, screenshot):
        """Creating a new collection should redirect to the editor."""
        authenticated_page.goto("/my/collections")
        screenshot(authenticated_page, "my-collections-before-create")

        authenticated_page.goto("/my/collections/new")
        authenticated_page.wait_for_url("**/my/collections/*/edit")
        screenshot(authenticated_page, "new-collection-editor")

        editor = CollectionEditorPage(authenticated_page)
        editor.wait_for_ready()
        assert editor.heading.lower() == "add new collection"
        expect(authenticated_page).to_have_url(
            re.compile(rf"{BASE_URL}/my/collections/.+/edit")
        )

        editor.delete()

    def test_new_collection_has_empty_title(self, authenticated_page: Page, screenshot):
        """A new collection should have a placeholder title, not a filled value."""
        url = create_draft_collection(authenticated_page)
        screenshot(authenticated_page, "new-collection-title")

        editor = CollectionEditorPage(authenticated_page)
        title_value = editor.get_title()
        assert title_value == ""

        editor.delete()

    def test_new_collection_appears_in_drafts_list(self, authenticated_page: Page, screenshot):
        """A newly created collection should appear in the drafts list."""
        url = create_draft_collection(authenticated_page)
        screenshot(authenticated_page, "new-collection-created")

        authenticated_page.goto("/my/collections")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "drafts-list-with-new-collection")

        drafts_table = authenticated_page.locator("#table-unpublished-collections")
        expect(drafts_table).to_contain_text("Untitled collection")

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        CollectionEditorPage(authenticated_page).wait_for_ready()
        CollectionEditorPage(authenticated_page).delete()


# ---------------------------------------------------------------------------
# Edit collection tests
# ---------------------------------------------------------------------------


@pytest.mark.collections
class TestEditCollection:
    """Test editing collection metadata fields."""

    def test_edit_title_and_save(self, authenticated_page: Page, screenshot):
        """Editing the title and saving should persist the change."""
        url = create_draft_collection(authenticated_page)
        editor = CollectionEditorPage(authenticated_page)
        screenshot(authenticated_page, "before-edit-title")

        editor.set_title("E2E Test Collection Title")
        editor.save()
        screenshot(authenticated_page, "after-save-title")

        # Reload to verify persistence
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        editor = CollectionEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "reloaded-after-save")

        assert editor.get_title() == "E2E Test Collection Title"

        editor.delete()

    def test_edit_description_and_save(self, authenticated_page: Page, screenshot):
        """Editing the description and saving should persist the change."""
        url = create_draft_collection(authenticated_page)
        editor = CollectionEditorPage(authenticated_page)

        editor.set_description("This is a test description for collection E2E.")
        editor.save()
        screenshot(authenticated_page, "after-save-description")

        # Reload to verify persistence
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        editor = CollectionEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "reloaded-description")

        description = editor.get_description_text()
        assert "This is a test description for collection E2E." in description

        editor.delete()

    def test_edit_title_reflected_in_drafts_list(self, authenticated_page: Page, screenshot):
        """A saved title should appear in the drafts list on /my/collections."""
        url = create_draft_collection(authenticated_page)
        editor = CollectionEditorPage(authenticated_page)

        test_title = f"Collection CRUD Test {uuid.uuid4().hex[:8]}"
        editor.set_title(test_title)
        editor.save()

        authenticated_page.goto("/my/collections")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "drafts-list-with-updated-title")

        drafts_table = authenticated_page.locator("#table-unpublished-collections")
        expect(drafts_table).to_contain_text(test_title)

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        CollectionEditorPage(authenticated_page).wait_for_ready()
        CollectionEditorPage(authenticated_page).delete()

    def test_editor_has_save_delete_and_publish_buttons(self, authenticated_page: Page, screenshot):
        """The collection editor should show Save, Delete, and Publish buttons."""
        url = create_draft_collection(authenticated_page)
        editor = CollectionEditorPage(authenticated_page)
        screenshot(authenticated_page, "editor-buttons")

        assert editor.is_save_visible()
        assert editor.is_delete_visible()
        assert editor.is_publish_visible()

        editor.delete()


# ---------------------------------------------------------------------------
# Delete collection tests
# ---------------------------------------------------------------------------


@pytest.mark.collections
class TestDeleteCollection:
    """Test deleting draft collections."""

    def test_delete_draft_collection(self, authenticated_page: Page, screenshot):
        """Deleting a draft collection should redirect to /my/collections."""
        url = create_draft_collection(authenticated_page)
        screenshot(authenticated_page, "before-delete")

        editor = CollectionEditorPage(authenticated_page)
        editor.delete()

        screenshot(authenticated_page, "after-delete")
        expect(authenticated_page).to_have_url(f"{BASE_URL}/my/collections")

    def test_deleted_collection_removed_from_drafts_list(self, authenticated_page: Page, screenshot):
        """A deleted collection should no longer appear in the drafts list."""
        url = create_draft_collection(authenticated_page)
        editor = CollectionEditorPage(authenticated_page)

        unique_title = f"DeleteMe-{uuid.uuid4().hex[:8]}"
        editor.set_title(unique_title)
        editor.save()

        # Verify it appears in the list first
        authenticated_page.goto("/my/collections")
        authenticated_page.wait_for_load_state("domcontentloaded")
        drafts_table = authenticated_page.locator("#table-unpublished-collections")
        expect(drafts_table).to_contain_text(unique_title)
        screenshot(authenticated_page, "before-delete-in-list")

        # Now delete it
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        CollectionEditorPage(authenticated_page).wait_for_ready()
        CollectionEditorPage(authenticated_page).delete()

        # Verify it's gone from the list
        authenticated_page.goto("/my/collections")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "after-delete-from-list")

        expect(authenticated_page.locator("body")).not_to_contain_text(unique_title)


# ---------------------------------------------------------------------------
# Add/remove datasets from collection tests
# ---------------------------------------------------------------------------


@pytest.mark.collections
class TestCollectionDatasets:
    """Test adding and removing datasets from a collection."""

    def test_add_dataset_to_collection_via_api(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """Adding a published dataset to a collection via API should show it in the list."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = CollectionEditorPage(authenticated_page)
        screenshot(authenticated_page, "collection-before-add-dataset")

        # Add the published dataset via API
        response = authenticated_page.request.post(
            f"/v2/account/collections/{container_uuid}/articles",
            data={"articles": [published_dataset]},
        )
        assert response.ok, f"Add dataset failed: {response.status} {response.text()}"

        # Reload to see the dataset in the list
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        editor = CollectionEditorPage(authenticated_page)
        editor.wait_for_ready()

        # Wait for the articles list to render
        authenticated_page.locator("#articles-list tbody tr").first.wait_for(
            state="visible", timeout=10000
        )
        screenshot(authenticated_page, "collection-with-dataset")

        assert editor.get_dataset_count() >= 1
        dataset_names = editor.get_dataset_names()
        assert any("Dataset for Collection Test" in name for name in dataset_names)

        editor.delete()

    def test_remove_dataset_from_collection_via_api(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """Removing a dataset from a collection via API should update the list."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)

        # Add a dataset
        authenticated_page.request.post(
            f"/v2/account/collections/{container_uuid}/articles",
            data={"articles": [published_dataset]},
        )

        # Remove the dataset
        response = authenticated_page.request.delete(
            f"/v2/account/collections/{container_uuid}/articles/{published_dataset}",
        )
        assert response.ok, f"Remove dataset failed: {response.status} {response.text()}"

        # Reload and verify dataset is gone
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        editor = CollectionEditorPage(authenticated_page)
        editor.wait_for_ready()

        # Give time for the articles list to render (if any)
        authenticated_page.wait_for_timeout(1000)
        screenshot(authenticated_page, "collection-after-remove-dataset")

        assert editor.get_dataset_count() == 0

        editor.delete()


# ---------------------------------------------------------------------------
# Collection access control tests
# ---------------------------------------------------------------------------


@pytest.mark.collections
class TestCollectionAccessControl:
    """Test access control for collection pages."""

    def test_collection_editor_requires_auth(self, page: Page, screenshot):
        """GET /my/collections/<uuid>/edit without a session should return 403."""
        fake_uuid = str(uuid.uuid4())
        response = page.goto(f"/my/collections/{fake_uuid}/edit")
        assert response is not None
        screenshot(page, "collection-editor-403")
        assert response.status == 403

    def test_nonexistent_collection_returns_404(self, page: Page, screenshot):
        """GET /collections/<fake-uuid> should return 404."""
        fake_uuid = str(uuid.uuid4())
        response = page.goto(f"/collections/{fake_uuid}")
        assert response is not None
        screenshot(page, "collection-404")
        assert response.status == 404

    def test_other_users_collection_not_accessible(self, admin_page: Page, screenshot):
        """A user should not be able to edit another user's draft collection."""
        url = create_draft_collection(admin_page)
        container_uuid = get_container_uuid_from_url(url)
        screenshot(admin_page, "admin-created-collection")

        # Impersonate a non-admin user
        non_admin_uuid = get_non_admin_account_uuid()
        impersonate(admin_page, non_admin_uuid)
        screenshot(admin_page, "impersonated-non-admin")

        # Try to access the admin's collection editor
        response = admin_page.goto(f"/my/collections/{container_uuid}/edit")
        assert response is not None
        screenshot(admin_page, "other-users-collection-denied")
        assert response.status == 403

        # Stop impersonation and clean up
        stop_impersonation(admin_page)
        admin_page.goto(url)
        admin_page.wait_for_load_state("domcontentloaded")
        CollectionEditorPage(admin_page).wait_for_ready()
        CollectionEditorPage(admin_page).delete()

    def test_my_collections_page_requires_auth(self, page: Page, screenshot):
        """GET /my/collections without a session should return 403."""
        response = page.goto("/my/collections")
        assert response is not None
        screenshot(page, "my-collections-403")
        assert response.status == 403


# ---------------------------------------------------------------------------
# Publish collection tests
# ---------------------------------------------------------------------------


@pytest.mark.collections
class TestPublishCollection:
    """Test the collection publish workflow."""

    def test_publish_collection_via_api(self, authenticated_page: Page, screenshot):
        """Publishing a collection via API should succeed."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        screenshot(authenticated_page, "before-publish")

        fill_required_fields_and_publish_collection(
            authenticated_page,
            container_uuid,
            title="Published Collection Test",
        )

        # Visit the public page
        response = authenticated_page.goto(f"/collections/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert response is not None
        screenshot(authenticated_page, "published-collection-public")
        assert response.status == 200

    def test_publish_collection_via_ui(self, authenticated_page: Page, screenshot):
        """Publishing a collection via the UI Publish button should redirect to success page."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = CollectionEditorPage(authenticated_page)

        # Fill required fields via API
        category_uuid = authenticated_page.evaluate(
            "() => { let c = document.querySelector(\"input[name='categories']\"); "
            "return c ? c.value : null; }"
        )

        authenticated_page.request.post(
            f"/v3/collections/{container_uuid}/tags",
            data={"tags": ["e2e-test", "ui-publish", "automated", "playwright"]},
        )
        authenticated_page.request.post(
            f"/v2/account/collections/{container_uuid}/authors",
            data={"authors": [{"first_name": "Test", "last_name": "Author"}]},
        )
        if category_uuid:
            authenticated_page.request.post(
                f"/v2/account/collections/{container_uuid}/categories",
                data={"categories": [category_uuid]},
            )

        # Set title and description in the editor
        editor.set_title("UI Publish Collection Test")
        editor.set_description("Test collection published via UI.")
        editor.save()

        # Reload editor so JS activate() can re-render API-added metadata
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        editor = CollectionEditorPage(authenticated_page)
        editor.wait_for_ready()

        # Wait for AJAX calls in activate() to finish rendering tags/authors/categories
        authenticated_page.locator("#tags-list li").first.wait_for(
            state="visible", timeout=10000
        )
        authenticated_page.locator("#authors-list tbody tr").first.wait_for(
            state="visible", timeout=10000
        )

        # Ensure group radio is checked (template pre-selects account's group,
        # but activate() may re-set it from API data)
        group_checked = authenticated_page.evaluate(
            "() => document.querySelector(\"input[name='groups']:checked\") !== null"
        )
        if not group_checked:
            # Click the first available group radio
            authenticated_page.locator("input[name='groups']").first.check()

        screenshot(authenticated_page, "before-ui-publish")

        # Publish via UI — intercept the publish API call to verify
        with authenticated_page.expect_response(
            lambda r: "/publish" in r.url, timeout=60000
        ) as response_info:
            authenticated_page.locator("#publish").click()

        publish_response = response_info.value
        assert publish_response.ok, (
            f"Publish API failed: {publish_response.status} "
            f"{publish_response.text()}"
        )

        # After successful publish, JS redirects via window.location.replace
        authenticated_page.wait_for_load_state("domcontentloaded", timeout=10000)
        screenshot(authenticated_page, "after-ui-publish")

        expect(authenticated_page.locator("h1")).to_contain_text(
            "Your collection has been published"
        )

    def test_published_collection_appears_in_published_list(
        self, authenticated_page: Page, screenshot
    ):
        """A published collection should appear in the published collections list."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)

        fill_required_fields_and_publish_collection(
            authenticated_page,
            container_uuid,
            title="Listed Published Collection",
        )

        authenticated_page.goto("/my/collections")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "published-collections-list")

        published_table = authenticated_page.locator("#table-published-collections")
        expect(published_table).to_contain_text("Listed Published Collection")

    def test_published_collection_shows_metadata(
        self, authenticated_page: Page, screenshot
    ):
        """The public collection page should display the collection metadata."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)

        fill_required_fields_and_publish_collection(
            authenticated_page,
            container_uuid,
            title="Metadata Display Collection",
            description="<p>Description for metadata display test.</p>",
        )

        response = authenticated_page.goto(f"/collections/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert response is not None
        assert response.status == 200
        screenshot(authenticated_page, "collection-metadata-display")

        expect(authenticated_page.locator("#metadata")).to_be_visible()

    def test_draft_collection_not_publicly_visible(self, authenticated_page: Page, screenshot):
        """A draft collection should not be viewable at /collections/<uuid>."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)

        response = authenticated_page.goto(f"/collections/{container_uuid}")
        assert response is not None
        screenshot(authenticated_page, "draft-not-public")
        assert response.status in (404, 410)

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        CollectionEditorPage(authenticated_page).wait_for_ready()
        CollectionEditorPage(authenticated_page).delete()

    def test_published_collection_with_dataset(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """A published collection containing a dataset should be linked via API."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)

        # Add dataset to collection
        response = authenticated_page.request.post(
            f"/v2/account/collections/{container_uuid}/articles",
            data={"articles": [published_dataset]},
        )
        assert response.ok

        # Verify dataset is listed in the draft collection via API
        response = authenticated_page.request.get(
            f"/v2/account/collections/{container_uuid}/articles",
        )
        assert response.ok
        datasets = response.json()
        screenshot(authenticated_page, "collection-datasets-api")
        assert len(datasets) >= 1

        fill_required_fields_and_publish_collection(
            authenticated_page,
            container_uuid,
            title="Collection With Dataset",
        )

        # Verify the published collection page is accessible
        response = authenticated_page.goto(f"/collections/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert response is not None
        assert response.status == 200
        screenshot(authenticated_page, "published-collection-with-dataset")

        # The datasets section should exist on the public page
        data_section = authenticated_page.locator("#data")
        expect(data_section).to_be_visible()


# ---------------------------------------------------------------------------
# Collection versioning tests
# ---------------------------------------------------------------------------


@pytest.mark.collections
class TestCollectionVersioning:
    """Test creating new versions of published collections."""

    def test_new_version_button_on_my_collections(
        self, authenticated_page: Page, screenshot
    ):
        """The published collections table should show a 'new version' button."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)

        fill_required_fields_and_publish_collection(
            authenticated_page,
            container_uuid,
            title="Version Button Collection",
        )

        authenticated_page.goto("/my/collections")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.locator("#table-published-collections").wait_for(state="visible")
        screenshot(authenticated_page, "my-collections-published")

        new_version_link = authenticated_page.locator(
            f'a[href="/my/collections/{container_uuid}/new-version-draft"]'
        )
        expect(new_version_link).to_be_visible()

    def test_create_new_version_draft(self, authenticated_page: Page, screenshot):
        """Creating a new version draft should redirect to the editor."""
        url = create_draft_collection(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)

        fill_required_fields_and_publish_collection(
            authenticated_page,
            container_uuid,
            title="New Version Collection",
        )

        # Re-login after publish
        authenticated_page.goto("/login")
        authenticated_page.wait_for_url("**/my/dashboard**")

        authenticated_page.goto(
            f"/my/collections/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/collections/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "new-version-editor")

        editor = CollectionEditorPage(authenticated_page)
        editor.wait_for_ready()

        assert editor.is_save_visible()
        assert editor.is_delete_visible()

        # Title should be preserved
        assert editor.get_title() == "New Version Collection"
        screenshot(authenticated_page, "new-version-draft-ready")

        editor.delete()
