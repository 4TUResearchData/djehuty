"""
Dataset versioning tests.

Covers:
    - Create new version draft from published dataset page
    - Navigate version history
    - Access specific version via URL
    - Verify metadata preserved in new version

Run with:
    cd e2e && python -m pytest tests/test_versioning.py -v
"""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from helpers.dataset import (
    create_draft_dataset,
    get_container_uuid_from_url,
)
from helpers.publish import fill_required_fields_and_publish
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_FILE_CONTENT = b"Versioning test file.\n"
TEST_FILE_NAME = "version-test-file.txt"

DATASET_TITLE_V1 = "Versioning Test Dataset V1"
DATASET_DESCRIPTION_V1 = "<p>First version of the versioning test dataset.</p>"


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    """Create a temporary test file and return its path."""
    file_path = tmp_path / TEST_FILE_NAME
    file_path.write_bytes(TEST_FILE_CONTENT)
    return str(file_path)


@pytest.fixture()
def published_dataset(authenticated_page: Page, test_file: str):
    """Create, publish, and return (page, container_uuid) for a published dataset."""
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(test_file)
    editor.save()

    fill_required_fields_and_publish(
        authenticated_page,
        container_uuid,
        title=DATASET_TITLE_V1,
        description=DATASET_DESCRIPTION_V1,
    )

    # Re-login after publish (publish flow may leave session in review state)
    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")

    # Wait for the published dataset to be accessible on the public page.
    # The SPARQL store may need a moment to reflect the published state.
    for _ in range(5):
        resp = authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        if resp and resp.status == 200 and authenticated_page.locator("#metadata").count() > 0:
            break
        authenticated_page.wait_for_timeout(3000)

    return container_uuid


# ---------------------------------------------------------------------------
# Create new version tests
# ---------------------------------------------------------------------------


@pytest.mark.versioning
class TestCreateNewVersion:
    """Test creating a new version draft from a published dataset."""

    def test_new_version_button_on_my_datasets(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """The published datasets table should show a 'new version' button."""
        container_uuid = published_dataset

        # The SPARQL store may need a moment to reflect the published state.
        # Retry with page reloads to handle eventual consistency.
        new_version_link = authenticated_page.locator(
            f'a[href="/my/datasets/{container_uuid}/new-version-draft"]'
        )
        for attempt in range(4):
            authenticated_page.goto("/my/datasets")
            authenticated_page.wait_for_load_state("domcontentloaded")
            authenticated_page.locator("#table-published").wait_for(
                state="visible", timeout=60000
            )
            if attempt == 0:
                screenshot(authenticated_page, "my-datasets-published")
            if new_version_link.count() > 0:
                break
            authenticated_page.wait_for_timeout(3000)

        expect(new_version_link).to_be_visible(timeout=10000)
        screenshot(authenticated_page, "new-version-button-visible")

    def test_create_new_version_draft(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """Clicking 'new version' should create a draft and redirect to editor."""
        container_uuid = published_dataset

        # Navigate to the new-version-draft URL
        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "new-version-editor")

        # Should be in the dataset editor
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        # Save and delete buttons should be visible (it's a draft)
        assert editor.is_save_visible()
        assert editor.is_delete_visible()
        screenshot(authenticated_page, "new-version-draft-ready")

        # Clean up the draft
        editor.delete()

    def test_new_version_preserves_title(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """A new version draft should preserve the title from the published version."""
        container_uuid = published_dataset

        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")

        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "new-version-title-check")

        # Title should be preserved from v1
        assert editor.get_title() == DATASET_TITLE_V1

        # Clean up
        editor.delete()

    def test_new_version_preserves_description(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """A new version draft should preserve the description from the published version."""
        container_uuid = published_dataset

        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")

        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "new-version-description-check")

        # Description text should be preserved (strip HTML tags for comparison)
        description_text = editor.get_description_text().strip()
        assert "First version of the versioning test dataset" in description_text

        # Clean up
        editor.delete()

    def test_new_version_preserves_files(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """A new version draft should preserve the files from the published version."""
        container_uuid = published_dataset

        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")

        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        # Wait for the files table to load (files are copied asynchronously)
        authenticated_page.locator("table#files tbody tr").first.wait_for(
            state="visible", timeout=15000
        )
        screenshot(authenticated_page, "new-version-files-check")

        # Files should be copied from v1
        assert editor.get_file_count() >= 1
        file_names = editor.get_file_names()
        assert TEST_FILE_NAME in file_names
        screenshot(authenticated_page, "new-version-files-preserved")

        # Clean up
        editor.delete()

    def test_existing_draft_redirects_to_editor(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """If a draft already exists, new-version-draft should redirect to the existing draft."""
        container_uuid = published_dataset

        # Create first draft
        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")
        first_url = authenticated_page.url
        screenshot(authenticated_page, "first-draft-created")

        # Try creating another draft — should redirect to the same editor
        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")
        second_url = authenticated_page.url
        screenshot(authenticated_page, "redirect-to-existing-draft")

        assert first_url == second_url

        # Clean up
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.delete()


# ---------------------------------------------------------------------------
# Version history tests
# ---------------------------------------------------------------------------


@pytest.mark.versioning
class TestVersionHistory:
    """Test version history navigation on the public dataset page."""

    def test_version_dropdown_visible_after_two_versions(
        self, authenticated_page: Page, published_dataset: str, test_file: str,
        screenshot
    ):
        """After publishing a second version, the version dropdown should appear."""
        container_uuid = published_dataset

        # Create and publish a second version
        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")

        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Versioning Test Dataset V2")
        editor.save()

        # Get the new container_uuid for the draft (same container)
        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Versioning Test Dataset V2",
            description="<p>Second version.</p>",
        )

        # Visit the public page
        authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "public-page-v2")

        # Version dropdown should be visible (only when >1 version)
        versions_btn = authenticated_page.locator("#versions-btn")
        expect(versions_btn).to_be_visible()
        screenshot(authenticated_page, "version-dropdown-visible")

    def test_version_dropdown_lists_all_versions(
        self, authenticated_page: Page, published_dataset: str, test_file: str,
        screenshot
    ):
        """The version dropdown should list all published versions."""
        container_uuid = published_dataset

        # Create and publish v2
        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")

        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.save()

        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Versioning Test Dataset V2 List",
            description="<p>Second version for listing.</p>",
        )

        # Visit the public page
        authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")

        # Click the version dropdown to reveal entries
        authenticated_page.locator("#versions-btn").click()
        authenticated_page.wait_for_timeout(500)
        screenshot(authenticated_page, "version-dropdown-expanded")

        # Should show version 1 and version 2
        versions_div = authenticated_page.locator("#versions")
        expect(versions_div).to_contain_text("Version 1")
        expect(versions_div).to_contain_text("Version 2")

    def test_navigate_to_older_version(
        self, authenticated_page: Page, published_dataset: str, test_file: str,
        screenshot
    ):
        """Clicking version 1 in the dropdown should navigate to that version."""
        container_uuid = published_dataset

        # Create and publish v2
        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")

        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.save()

        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Versioning Test Dataset V2 Nav",
            description="<p>Second version for navigation.</p>",
        )

        # Visit the latest version page
        authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "latest-version-before-nav")

        # Click dropdown and navigate to version 1
        authenticated_page.locator("#versions-btn").click()
        authenticated_page.wait_for_timeout(500)
        authenticated_page.locator(
            f'#versions a[href="/datasets/{container_uuid}/1"]'
        ).click()
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "navigated-to-v1")

        # URL should contain version 1
        assert f"/datasets/{container_uuid}/1" in authenticated_page.url

        # Should show "old" styling indicator
        versions_btn = authenticated_page.locator("#versions-btn")
        expect(versions_btn).to_contain_text("(old)")


# ---------------------------------------------------------------------------
# Access specific version via URL
# ---------------------------------------------------------------------------


@pytest.mark.versioning
class TestVersionAccess:
    """Test accessing specific versions via URL."""

    def test_access_version_1_directly(
        self, authenticated_page: Page, published_dataset: str, test_file: str,
        screenshot
    ):
        """Version 1 should be accessible directly via /datasets/<uuid>/1."""
        container_uuid = published_dataset

        # Create and publish v2 so version 1 is an older version
        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")

        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.save()

        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Versioning Test V2 Access",
            description="<p>Second version for access test.</p>",
        )

        # Access version 1 directly
        response = authenticated_page.goto(f"/datasets/{container_uuid}/1")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "direct-access-v1")

        assert response is not None
        assert response.status == 200
        expect(authenticated_page.locator("#metadata")).to_be_visible()

    def test_access_latest_version_via_container_url(
        self, authenticated_page: Page, published_dataset: str, test_file: str,
        screenshot
    ):
        """The container URL without version should show the latest version."""
        container_uuid = published_dataset

        # Create and publish v2
        authenticated_page.goto(
            f"/my/datasets/{container_uuid}/new-version-draft"
        )
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")

        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.set_title("Versioning Latest Check V2")
        editor.save()

        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Versioning Latest Check V2",
            description="<p>Second version for latest check.</p>",
        )

        # Access via container URL (no version)
        response = authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "container-url-latest")

        assert response is not None
        assert response.status == 200

        # Should show the latest version (version 2)
        versions_btn = authenticated_page.locator("#versions-btn")
        expect(versions_btn).to_contain_text("Version 2")
        # Should NOT show "(old)" since it's the latest
        expect(versions_btn).not_to_contain_text("(old)")

    def test_access_version_via_api(
        self, authenticated_page: Page, published_dataset: str, screenshot
    ):
        """The versions API endpoint should list all published versions."""
        container_uuid = published_dataset

        # V1 is already published. Check API.
        response = authenticated_page.request.get(
            f"/v2/articles/{container_uuid}/versions"
        )
        assert response.ok
        versions = response.json()
        screenshot(authenticated_page, "api-versions-v1-only")

        assert len(versions) >= 1
        assert any(v["version"] == 1 for v in versions)
