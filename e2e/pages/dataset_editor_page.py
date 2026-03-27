"""
Page object for the dataset editor (/my/datasets/<id>/edit).
"""

import re

from playwright.sync_api import Page, expect

from pages.base_page import BasePage


class DatasetEditorPage(BasePage):
    """Interact with the dataset creation / editing form."""

    def __init__(self, page: Page):
        super().__init__(page)
        self._container_uuid = None

    def wait_for_ready(self):
        """Wait until the editor JS has loaded (content becomes visible)."""
        self.page.locator(".article-content").wait_for(state="visible")

    def set_title(self, title: str):
        self.page.locator("#title").fill(title)

    def get_title(self) -> str:
        return self.page.locator("#title").input_value()

    def set_description(self, description: str):
        editor = self.page.locator("#description .ql-editor")
        editor.click()
        editor.fill(description)

    def get_description_text(self) -> str:
        return self.page.locator("#description .ql-editor").inner_text()

    def save(self):
        self.page.locator("#save").click()
        self.page.locator("#message.success").wait_for(state="visible")

    def delete(self):
        # Wait for the content loader to disappear — this means activate()
        # has finished its AJAX call and bound click handlers.
        self.page.locator(".article-content-loader").wait_for(state="hidden")
        self.page.locator(".article-content").wait_for(state="visible")
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.locator("#delete").click()
        # The JS does: window.location.pathname = "/my/datasets" after AJAX DELETE
        self.page.wait_for_url("**/my/datasets", wait_until="domcontentloaded")

    def is_save_visible(self) -> bool:
        return self.page.locator("#save").is_visible()

    def is_delete_visible(self) -> bool:
        return self.page.locator("#delete").is_visible()

    def is_submit_visible(self) -> bool:
        return self.page.locator("#submit").is_visible()

    @property
    def heading(self) -> str:
        return self.page.locator(".article-content h1").inner_text()

    # ------------------------------------------------------------------
    # Record type
    # ------------------------------------------------------------------

    def select_record_type(self, record_type: str):
        """Select the record type radio button by clicking its label.

        Args:
            record_type: One of 'metadata_record_only', 'external_link',
                         'upload_files', 'upload_software'.
        """
        self.page.locator(f"label[for='{record_type}']").click()

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    @property
    def container_uuid(self) -> str:
        """Extract the container UUID from the current page URL."""
        if self._container_uuid is None:
            match = re.search(r"/my/datasets/([^/]+)/edit", self.page.url)
            if match:
                self._container_uuid = match.group(1)
        return self._container_uuid

    def upload_file(self, file_path: str, expected_count: int = 1):
        """Upload a file via the Dropzone file chooser dialog.

        Args:
            file_path: Path to the file to upload.
            expected_count: Expected total file count after this upload.
        """
        # The dropzone form must be visible (requires "File deposit" record type)
        self.page.locator("form#dropzone-field").wait_for(state="visible")
        with self.page.expect_file_chooser() as fc_info:
            self.page.locator("form#dropzone-field").click()
        fc_info.value.set_files(file_path)
        # Wait for the expected number of rows to appear in the files table.
        # Use a longer timeout because S3 uploads can be slow in CI.
        self.page.locator(
            f"table#files tbody tr:nth-child({expected_count})"
        ).wait_for(state="visible", timeout=60000)
        # Wait for Dropzone's AJAX re-render to finish before the next upload
        self.page.wait_for_load_state("networkidle")

    def get_file_rows(self):
        """Return the locator for all file rows in the files table."""
        return self.page.locator("table#files tbody tr")

    def get_file_count(self) -> int:
        """Return the number of files in the files table."""
        table = self.page.locator("table#files")
        if not table.is_visible():
            return 0
        return self.get_file_rows().count()

    def get_file_names(self) -> list[str]:
        """Return list of filenames shown in the files table."""
        rows = self.get_file_rows()
        names = []
        for i in range(rows.count()):
            link = rows.nth(i).locator("td:first-child a").first
            names.append(link.inner_text())
        return names

    def get_file_sizes(self) -> list[str]:
        """Return list of file size labels shown in the files table."""
        rows = self.get_file_rows()
        sizes = []
        for i in range(rows.count()):
            size_badge = rows.nth(i).locator("span.file-size")
            if size_badge.is_visible():
                sizes.append(size_badge.inner_text())
        return sizes

    def get_file_md5s(self) -> list[str]:
        """Return list of MD5 checksums shown in the files table."""
        rows = self.get_file_rows()
        md5s = []
        for i in range(rows.count()):
            md5_cell = rows.nth(i).locator("td:nth-child(2)")
            md5s.append(md5_cell.inner_text().strip())
        return md5s

    def remove_file(self, index: int = 0):
        """Remove a file by clicking the trash icon on the given row."""
        row = self.get_file_rows().nth(index)
        self.page.once("dialog", lambda dialog: dialog.accept())
        row.locator("a.fa-trash-can").click()

    def remove_all_files(self):
        """Click the 'Remove all files' button."""
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.locator("#remove-all-files").click()

    def get_file_download_url(self, index: int = 0) -> str:
        """Return the download URL for the file at the given row index."""
        row = self.get_file_rows().nth(index)
        return row.locator("td:first-child a").first.get_attribute("href")
