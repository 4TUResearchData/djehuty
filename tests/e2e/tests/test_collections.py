"""
Collection management tests.
"""

import re
import uuid

import pytest
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
from playwright.sync_api import Page, expect

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
        expect(authenticated_page).to_have_url(re.compile(rf"{BASE_URL}/my/collections/.+/edit"))

        editor.delete()

    def test_new_collection_has_empty_title(self, authenticated_page: Page, screenshot):
        """A new collection should have a placeholder title, not a filled value."""
        create_draft_collection(authenticated_page)
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
        create_draft_collection(authenticated_page)
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
        create_draft_collection(authenticated_page)
        screenshot(authenticated_page, "before-delete")

        editor = CollectionEditorPage(authenticated_page)
        editor.delete()

        screenshot(authenticated_page, "after-delete")
        expect(authenticated_page).to_have_url(f"{BASE_URL}/my/collections")

    def test_deleted_collection_removed_from_drafts_list(
        self, authenticated_page: Page, screenshot
    ):
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
        authenticated_page.locator("#tags-list li").first.wait_for(state="visible", timeout=10000)
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
            f"Publish API failed: {publish_response.status} {publish_response.text()}"
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

    def test_published_collection_shows_metadata(self, authenticated_page: Page, screenshot):
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

    def test_new_version_button_on_my_collections(self, authenticated_page: Page, screenshot):
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

        authenticated_page.goto(f"/my/collections/{container_uuid}/new-version-draft")
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


# ---------------------------------------------------------------------------
# COLLECT button tests
# ---------------------------------------------------------------------------


def _create_titled_draft_collection(page: Page, title: str) -> str:
    """Create a draft collection with a title via the API.

    Returns the container UUID. Used instead of the UI helper because the
    COLLECT menu labels its entries by title, so the collections under test
    have to be distinguishable from one another.
    """
    response = page.request.post("/v2/account/collections", data={"title": title})
    assert response.ok, f"Create collection failed: {response.status} {response.text()}"
    return response.json()["location"].rstrip("/").split("/")[-1]


def _collection_contains_dataset(page: Page, container_uuid: str, dataset_uuid: str) -> bool:
    """Return whether a collection lists the given dataset container."""
    response = page.request.get(
        f"/v2/account/collections/{container_uuid}/articles",
        params={"limit": 10000},
    )
    assert response.ok, f"List datasets failed: {response.status} {response.text()}"
    return any(record.get("uuid") == dataset_uuid for record in response.json())


@pytest.mark.collections
class TestCollectButton:
    """Tests for the COLLECT button on a dataset landing page."""

    def test_collect_adds_to_the_clicked_collection(
        self, authenticated_page: Page, published_dataset, screenshot
    ):
        """Clicking an entry in the COLLECT menu adds the dataset to that
        collection, and not to whichever entry happens to be listed last.
        Regression test for #218.

        Two collections are required. With only one, the last entry is also the
        entry being clicked, and the defect cannot be observed.

        Every collection is exercised rather than just one, because the menu
        order is not something this test controls. Clicking each in turn guarantees
        that at least one click targets a non-last entry, which is the case that
        fails when the defect is present.
        """

        marker = uuid.uuid4().hex[:8]
        titles = [f"Collect Alpha {marker}", f"Collect Beta {marker}"]
        collections: dict[str, str] = {}

        try:
            for title in titles:
                collections[title] = _create_titled_draft_collection(authenticated_page, title)

            for title, container_uuid in collections.items():
                # Reload between clicks so the menu is rebuilt from scratch,
                # the same way a user arriving at the page would see it.
                authenticated_page.goto(f"/datasets/{published_dataset}")
                authenticated_page.wait_for_load_state("domcontentloaded")

                authenticated_page.locator("#collect-btn").click()
                entries = authenticated_page.locator("#collect ul a")
                expect(entries.first).to_be_visible()
                screenshot(authenticated_page, f"collect-menu-{title.split()[1].lower()}")

                assert entries.count() >= 2, (
                    "At least two collections must be listed for the defect to "
                    f"be observable, got {entries.all_inner_texts()}"
                )

                # Locate by title rather than by index: the account may own
                # collections beyond the two created here, and their position
                # in the menu is not guaranteed.
                #
                # /v2/account/collections lists every version node, so a
                # collection with published versions appears once per version,
                # each entry carrying the same title and container UUID. The
                # collections created here are fresh drafts and so appear once,
                # but match on .first regardless: any entry for a given title
                # points at the same collection.
                entry = entries.filter(has_text=title).first
                expect(entry).to_be_visible()
                entry.click()

                expect(authenticated_page.locator("#message")).to_contain_text(
                    "added to collection"
                )
                screenshot(authenticated_page, f"collect-added-{title.split()[1].lower()}")

                assert _collection_contains_dataset(
                    authenticated_page, container_uuid, published_dataset
                ), (
                    f"Clicking {title!r} did not add the dataset to that "
                    "collection. Under #218 every entry added the dataset to "
                    "whichever collection happened to be listed last."
                )
        finally:
            for container_uuid in collections.values():
                authenticated_page.request.delete(f"/v2/account/collections/{container_uuid}")

    def test_collect_menu_dedupes_versions_to_latest(
        self, authenticated_page: Page, published_dataset, screenshot
    ):
        """A collection with multiple published versions should appear once in
        the collection menu, labelled with its latest version.
        """
        marker = uuid.uuid4().hex[:8]
        title = f"Collect Versioned {marker}"
        container_uuid = _create_titled_draft_collection(authenticated_page, title)

        fill_required_fields_and_publish_collection(authenticated_page, container_uuid, title=title)
        authenticated_page.goto(f"/my/collections/{container_uuid}/new-version-draft")
        authenticated_page.wait_for_url("**/my/collections/*/edit")
        fill_required_fields_and_publish_collection(authenticated_page, container_uuid, title=title)

        try:
            authenticated_page.goto(f"/datasets/{published_dataset}")
            authenticated_page.wait_for_load_state("domcontentloaded")
            authenticated_page.locator("#collect-btn").click()

            entries = authenticated_page.locator("#collect-published li a").filter(has_text=title)
            expect(entries.first).to_be_visible()
            screenshot(authenticated_page, "collect-menu-deduped-versions")

            assert entries.count() == 1, (
                f"Expected exactly one entry for {title!r} across both published "
                f"versions, got {entries.count()}: {entries.all_inner_texts()}"
            )
            assert "(v2)" in entries.first.inner_text(), (
                f"Expected the deduped entry to show the latest version, got "
                f"{entries.first.inner_text()!r}"
            )
        finally:
            authenticated_page.request.delete(f"/v2/account/collections/{container_uuid}")

    def test_collect_menu_separates_published_and_draft_collections(
        self, authenticated_page: Page, published_dataset, screenshot
    ):
        """Draft and published collections should render in separate lists, with
        only published entries carrying a version label.
        """
        marker = uuid.uuid4().hex[:8]
        draft_title = f"Collect Draft {marker}"
        published_title = f"Collect Published {marker}"

        draft_uuid = _create_titled_draft_collection(authenticated_page, draft_title)
        published_uuid = _create_titled_draft_collection(authenticated_page, published_title)
        fill_required_fields_and_publish_collection(
            authenticated_page, published_uuid, title=published_title
        )

        try:
            authenticated_page.goto(f"/datasets/{published_dataset}")
            authenticated_page.wait_for_load_state("domcontentloaded")
            authenticated_page.locator("#collect-btn").click()
            screenshot(authenticated_page, "collect-menu-draft-vs-published")

            draft_entry = authenticated_page.locator("#collect-drafts li a").filter(
                has_text=draft_title
            )
            published_entry = authenticated_page.locator("#collect-published li a").filter(
                has_text=published_title
            )

            expect(draft_entry).to_be_visible()
            expect(published_entry).to_be_visible()
            assert "(v" not in draft_entry.inner_text()
            assert "(v1)" in published_entry.inner_text()
            expect(authenticated_page.locator("#collect-separator")).to_be_visible()
        finally:
            authenticated_page.request.delete(f"/v2/account/collections/{draft_uuid}")
            authenticated_page.request.delete(f"/v2/account/collections/{published_uuid}")

    def test_collect_menu_lists_alphabetically(
        self, authenticated_page: Page, published_dataset, screenshot
    ):
        """Entries within each collection menu section should be sorted
        alphabetically by title.
        """
        marker = uuid.uuid4().hex[:8]
        titles = [f"Zebra {marker}", f"Alpha {marker}", f"Mike {marker}"]
        collections = {t: _create_titled_draft_collection(authenticated_page, t) for t in titles}

        try:
            authenticated_page.goto(f"/datasets/{published_dataset}")
            authenticated_page.wait_for_load_state("domcontentloaded")
            authenticated_page.locator("#collect-btn").click()

            entries = authenticated_page.locator("#collect-drafts li a")
            expect(entries.first).to_be_visible()
            screenshot(authenticated_page, "collect-menu-alphabetical")

            texts = [t for t in entries.all_inner_texts() if marker in t]
            assert texts == sorted(texts), f"Expected alphabetical order, got {texts}"
        finally:
            for container_uuid in collections.values():
                authenticated_page.request.delete(f"/v2/account/collections/{container_uuid}")
