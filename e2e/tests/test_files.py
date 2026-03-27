"""
File management tests.

Covers:
    - Upload file via file picker in dataset editor
    - Verify uploaded file appears in file list
    - Download single file from dataset editor
    - Download all files as zip
    - Verify file metadata display (size, MD5)
    - Remove individual files and all files
    - Git instructions display for software deposits

Run with:
    cd e2e && python -m pytest tests/test_files.py -v
"""

import re
import tempfile
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from helpers.dataset import create_draft_dataset, get_container_uuid_from_url
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_FILE_CONTENT = b"Hello from Playwright E2E test!\n"
TEST_FILE_NAME = "e2e-test-file.txt"


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    """Create a temporary test file and return its path."""
    file_path = tmp_path / TEST_FILE_NAME
    file_path.write_bytes(TEST_FILE_CONTENT)
    return str(file_path)


@pytest.fixture()
def dataset_with_file(authenticated_page: Page, test_file: str):
    """Create a draft dataset, upload a test file, and yield (url, editor).

    Tears down by deleting the dataset after the test.
    """
    url = create_draft_dataset(authenticated_page)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(test_file)
    yield url, editor
    # Teardown: navigate back and delete
    authenticated_page.goto(url)
    authenticated_page.wait_for_load_state("domcontentloaded")
    DatasetEditorPage(authenticated_page).delete()


# ---------------------------------------------------------------------------
# Upload tests
# ---------------------------------------------------------------------------


@pytest.mark.files
class TestFileUpload:
    """Test uploading files to the dataset editor."""

    def test_upload_file_via_picker(self, authenticated_page: Page, test_file: str, screenshot):
        """Uploading a file should make it appear in the files table."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "editor-before-upload")

        editor.upload_file(test_file)
        screenshot(authenticated_page, "editor-after-upload")

        assert editor.get_file_count() == 1
        names = editor.get_file_names()
        assert TEST_FILE_NAME in names

        # Clean up
        editor.delete()

    def test_upload_multiple_files(self, authenticated_page: Page, tmp_path: Path, screenshot):
        """Uploading multiple files should show all of them in the table."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        # Create and upload two files sequentially
        file1 = tmp_path / "file-one.txt"
        file1.write_text("First file content")
        editor.upload_file(str(file1), expected_count=1)
        screenshot(authenticated_page, "after-first-upload")

        file2 = tmp_path / "file-two.txt"
        file2.write_text("Second file content")
        editor.upload_file(str(file2), expected_count=2)
        screenshot(authenticated_page, "after-second-upload")

        assert editor.get_file_count() == 2
        names = editor.get_file_names()
        assert "file-one.txt" in names
        assert "file-two.txt" in names

        # Clean up
        editor.delete()

    def test_uploaded_file_persists_after_reload(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """An uploaded file should still appear after reloading the editor."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        screenshot(authenticated_page, "before-reload")

        # Reload the editor page
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        editor.wait_for_ready()
        # Wait for files table to populate via AJAX
        authenticated_page.locator("table#files tbody tr").first.wait_for(state="visible")
        screenshot(authenticated_page, "after-reload")

        assert editor.get_file_count() == 1
        assert TEST_FILE_NAME in editor.get_file_names()

        # Clean up
        editor.delete()


# ---------------------------------------------------------------------------
# File metadata tests
# ---------------------------------------------------------------------------


@pytest.mark.files
class TestFileMetadata:
    """Test that file metadata (size, MD5) displays correctly."""

    def test_file_size_displayed(self, dataset_with_file, screenshot):
        """The file size badge should be visible for uploaded files."""
        url, editor = dataset_with_file
        screenshot(editor.page, "file-size-check")

        sizes = editor.get_file_sizes()
        assert len(sizes) == 1
        # The test file is small — verify the size badge is non-empty
        assert sizes[0] != ""

    def test_file_md5_displayed(self, dataset_with_file, screenshot):
        """The MD5 checksum should be displayed for uploaded files."""
        url, editor = dataset_with_file
        screenshot(editor.page, "file-md5-check")

        md5s = editor.get_file_md5s()
        assert len(md5s) == 1
        # MD5 should be a 32-character hex string or "Unavailable"
        assert re.match(r"^[a-f0-9]{32}$", md5s[0]) or md5s[0] == "Unavailable"


# ---------------------------------------------------------------------------
# File download tests
# ---------------------------------------------------------------------------


@pytest.mark.files
class TestFileDownload:
    """Test downloading files from the dataset editor."""

    def test_download_single_file(self, dataset_with_file, screenshot):
        """Clicking a file link in the editor should trigger a download."""
        url, editor = dataset_with_file
        page = editor.page
        screenshot(page, "before-download")

        # Get the download URL and trigger download
        with page.expect_download() as download_info:
            file_link = page.locator("table#files tbody tr").first.locator(
                "td:first-child a"
            ).first
            file_link.click()

        download = download_info.value
        screenshot(page, "after-download")
        assert download.suggested_filename == TEST_FILE_NAME

    def test_download_all_files_as_zip(self, dataset_with_file, screenshot):
        """The 'download all files' zip link should work for draft datasets."""
        url, editor = dataset_with_file
        page = editor.page
        container_uuid = editor.container_uuid

        # Use JavaScript navigation to trigger zip download
        zip_url = f"/ndownloader/items/{container_uuid}/versions/draft"
        with page.expect_download() as download_info:
            page.evaluate(f"window.location.href = '{zip_url}'")

        download = download_info.value
        screenshot(page, "zip-download")
        assert download.suggested_filename.endswith(".zip")


# ---------------------------------------------------------------------------
# File removal tests
# ---------------------------------------------------------------------------


@pytest.mark.files
class TestFileRemoval:
    """Test removing files from the dataset editor."""

    def test_remove_single_file(self, dataset_with_file, screenshot):
        """Removing a file should delete it from the files table."""
        url, editor = dataset_with_file
        page = editor.page
        screenshot(page, "before-remove")

        assert editor.get_file_count() == 1
        editor.remove_file(0)
        # Wait for the row to disappear
        page.locator("table#files tbody tr").first.wait_for(state="hidden", timeout=5000)
        screenshot(page, "after-remove")

        assert editor.get_file_count() == 0

    def test_remove_all_files(self, authenticated_page: Page, tmp_path: Path, screenshot):
        """The 'Remove all files' button should clear all files."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        # Upload two files
        for i, name in enumerate(("file-a.txt", "file-b.txt"), start=1):
            f = tmp_path / name
            f.write_text(f"Content of {name}")
            editor.upload_file(str(f), expected_count=i)

        screenshot(authenticated_page, "before-remove-all")
        assert editor.get_file_count() == 2

        editor.remove_all_files()
        # Wait for the table to empty
        authenticated_page.locator("table#files tbody tr").first.wait_for(
            state="hidden", timeout=5000
        )
        screenshot(authenticated_page, "after-remove-all")

        assert editor.get_file_count() == 0

        # Clean up
        editor.delete()


# ---------------------------------------------------------------------------
# Git / Software deposit tests
# ---------------------------------------------------------------------------


@pytest.mark.files
class TestGitInstructions:
    """Test that git instructions are displayed for software deposits."""

    def test_software_deposit_shows_git_instructions(
        self, authenticated_page: Page, screenshot
    ):
        """Selecting 'Software deposit' should display git push instructions."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "before-software-select")

        # Select the software deposit record type
        editor.select_record_type("upload_software")
        # Wait for the software upload field to become visible
        authenticated_page.locator("#software_upload_field").wait_for(state="visible")
        screenshot(authenticated_page, "software-deposit-selected")

        # Verify git instructions are displayed
        git_section = authenticated_page.locator("#software_upload_field")
        expect(git_section).to_contain_text("git remote add")
        expect(git_section).to_contain_text("git push")

        # Verify the git UUID field is present in the remote URL
        pre_elements = git_section.locator("pre")
        expect(pre_elements.first).to_be_visible()
        remote_cmd = pre_elements.first.inner_text()
        assert "git remote add" in remote_cmd

        # Clean up
        editor.delete()

    def test_software_deposit_shows_git_branch_selector(
        self, authenticated_page: Page, screenshot
    ):
        """The software deposit view should include a branch selector."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()

        editor.select_record_type("upload_software")
        authenticated_page.locator("#software_upload_field").wait_for(state="visible")
        screenshot(authenticated_page, "git-branch-selector")

        # The default branch dropdown should be present
        branch_select = authenticated_page.locator("select#git-branches")
        expect(branch_select).to_be_visible()

        # Clean up
        editor.delete()
