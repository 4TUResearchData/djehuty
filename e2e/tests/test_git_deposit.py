"""
Git software deposit tests.

Covers:
    - Create a software deposit and extract git remote URL
    - Initialize a local git repo and push to the dataset
    - Verify pushed files appear in the dataset's file list
    - Verify file metadata after git deposit
    - Verify git branch selector updates after push

Run with:
    cd e2e && python -m pytest tests/test_git_deposit.py -v
"""

import re
import subprocess
import tempfile
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from config import BASE_URL
from helpers.dataset import create_draft_dataset
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_git_remote_url(page: Page) -> str:
    """Extract the git remote URL from the software upload instructions.

    The URL shown in the UI uses the public base_url (e.g. localhost:9001),
    but inside Docker the app listens on localhost:8080.  We rewrite the URL
    to match E2E_BASE_URL so that ``git push`` works from inside the
    container.
    """
    git_section = page.locator("#software_upload_field")
    pre_text = git_section.locator("pre").first.inner_text()
    # Format: git remote add <shorttag> <url>
    match = re.search(r"git remote add \S+ (\S+\.git)", pre_text)
    if not match:
        raise ValueError(f"Cannot extract git remote URL from: {pre_text}")
    raw_url = match.group(1)
    # Replace the host:port with the E2E base URL so git can reach the app
    path = re.sub(r"^https?://[^/]+", "", raw_url)
    return f"{BASE_URL}{path}"


def create_local_git_repo(directory: Path, files: dict[str, str]) -> None:
    """Initialize a git repo in directory with the given files.

    Args:
        directory: Path to create the repo in.
        files: Dict of filename -> content to create and commit.
    """
    subprocess.run(
        ["git", "init"], cwd=directory, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "e2e@test.com"],
        cwd=directory, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "E2E Test"],
        cwd=directory, check=True, capture_output=True
    )
    for name, content in files.items():
        file_path = directory / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    subprocess.run(
        ["git", "add", "."], cwd=directory, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=directory, check=True, capture_output=True
    )


def git_push(directory: Path, remote_url: str) -> subprocess.CompletedProcess:
    """Add remote and push all branches."""
    subprocess.run(
        ["git", "remote", "add", "djehuty", remote_url],
        cwd=directory, check=True, capture_output=True
    )
    result = subprocess.run(
        ["git", "push", "djehuty", "--all"],
        cwd=directory, capture_output=True, text=True
    )
    return result


@pytest.fixture()
def software_dataset(authenticated_page: Page):
    """Create a draft dataset in software deposit mode and yield (url, editor, git_url).

    Tears down by deleting the dataset after the test.
    """
    url = create_draft_dataset(authenticated_page)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()

    # Switch to software deposit mode
    editor.select_record_type("upload_software")
    authenticated_page.locator("#software_upload_field").wait_for(state="visible")

    # Extract the git remote URL
    git_url = extract_git_remote_url(authenticated_page)

    yield url, editor, git_url

    # Teardown: navigate back and delete
    authenticated_page.goto(url)
    authenticated_page.wait_for_load_state("domcontentloaded")
    DatasetEditorPage(authenticated_page).delete()


# ---------------------------------------------------------------------------
# Git deposit workflow tests
# ---------------------------------------------------------------------------


@pytest.mark.git
class TestGitDeposit:
    """Test the full git software deposit workflow."""

    def test_extract_git_remote_url(self, software_dataset, screenshot):
        """The git instructions should contain a valid remote URL."""
        url, editor, git_url = software_dataset
        screenshot(editor.page, "git-remote-url")

        assert git_url.endswith(".git")
        assert "/v3/datasets/" in git_url

    def test_git_push_succeeds(self, software_dataset, screenshot):
        """Pushing a local repo to the dataset git remote should succeed."""
        url, editor, git_url = software_dataset
        screenshot(editor.page, "before-git-push")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)
            create_local_git_repo(repo_dir, {
                "README.md": "# Test Software\n\nThis is a test.\n",
                "main.py": "print('Hello from E2E test')\n",
            })

            result = git_push(repo_dir, git_url)
            assert result.returncode == 0, (
                f"git push failed: {result.stderr}"
            )

        screenshot(editor.page, "after-git-push")

    def test_pushed_files_appear_in_editor(self, software_dataset, screenshot):
        """After pushing, the git file list should show the pushed files."""
        url, editor, git_url = software_dataset
        page = editor.page

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)
            create_local_git_repo(repo_dir, {
                "README.md": "# Test Project\n",
                "app.py": "print('hello')\n",
            })
            result = git_push(repo_dir, git_url)
            assert result.returncode == 0, f"git push failed: {result.stderr}"

        # Refresh the git files list
        page.locator("#refresh-git-files").click()
        # Wait for the file list to populate
        page.locator("#git-files li").first.wait_for(state="visible", timeout=15000)
        screenshot(page, "git-files-listed")

        git_files = page.locator("#git-files li")
        file_count = git_files.count()
        assert file_count >= 2, f"Expected at least 2 files, got {file_count}"

        # Collect all file names
        file_names = [git_files.nth(i).inner_text() for i in range(file_count)]
        file_text = " ".join(file_names)
        assert "README.md" in file_text
        assert "app.py" in file_text

    def test_git_branch_selector_updates(self, software_dataset, screenshot):
        """After pushing, the branch selector should show the pushed branch."""
        url, editor, git_url = software_dataset
        page = editor.page

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)
            create_local_git_repo(repo_dir, {
                "file.txt": "content\n",
            })
            result = git_push(repo_dir, git_url)
            assert result.returncode == 0, f"git push failed: {result.stderr}"

        # Refresh the git files (which also refreshes branches)
        page.locator("#refresh-git-files").click()
        page.locator("#git-files li").first.wait_for(state="visible", timeout=15000)
        screenshot(page, "git-branches-after-push")

        # The branch selector should have at least one option besides the placeholder
        branch_select = page.locator("select#git-branches")
        expect(branch_select).to_be_visible()
        options = branch_select.locator("option:not([disabled])")
        assert options.count() >= 1, "Expected at least one branch option"

    def test_git_push_multiple_files(self, software_dataset, screenshot):
        """Pushing a repo with multiple flat files should show all of them."""
        url, editor, git_url = software_dataset
        page = editor.page

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)
            create_local_git_repo(repo_dir, {
                "README.md": "# Multi-file Test\n",
                "setup.py": "from setuptools import setup\nsetup(name='test')\n",
                "main.py": "def main(): pass\n",
                "utils.py": "def helper(): pass\n",
            })
            result = git_push(repo_dir, git_url)
            assert result.returncode == 0, f"git push failed: {result.stderr}"

        page.locator("#refresh-git-files").click()
        page.locator("#git-files li").first.wait_for(state="visible", timeout=15000)
        screenshot(page, "multiple-git-files")

        git_files = page.locator("#git-files li")
        file_count = git_files.count()
        assert file_count >= 4, f"Expected at least 4 files, got {file_count}"

    def test_git_push_preserves_after_reload(self, software_dataset, screenshot):
        """Pushed files should persist after reloading the editor page."""
        url, editor, git_url = software_dataset
        page = editor.page

        # Save the record type so it persists on reload
        editor.save()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)
            create_local_git_repo(repo_dir, {
                "persistent.txt": "This should persist.\n",
            })
            result = git_push(repo_dir, git_url)
            assert result.returncode == 0, f"git push failed: {result.stderr}"

        # Reload the editor page
        page.goto(url)
        page.wait_for_load_state("domcontentloaded")
        editor.wait_for_ready()

        # The software upload field should be visible (record type was saved)
        page.locator("#software_upload_field").wait_for(state="visible", timeout=10000)
        screenshot(page, "before-reload-check")

        # Wait for git files to load
        page.locator("#git-files li").first.wait_for(state="visible", timeout=15000)
        screenshot(page, "after-reload-files-visible")

        git_files = page.locator("#git-files li")
        file_names = [git_files.nth(i).inner_text() for i in range(git_files.count())]
        file_text = " ".join(file_names)
        assert "persistent.txt" in file_text
