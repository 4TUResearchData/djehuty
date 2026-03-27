"""
Page object for the collection editor (/my/collections/<id>/edit).
"""

import re

from playwright.sync_api import Page

from pages.base_page import BasePage


class CollectionEditorPage(BasePage):
    """Interact with the collection creation / editing form."""

    def __init__(self, page: Page):
        super().__init__(page)
        self._container_uuid = None

    def wait_for_ready(self):
        """Wait until the editor JS has loaded (content becomes visible)."""
        self.page.locator(".collection-content").wait_for(state="visible")

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
        self.page.locator(".collection-content-loader").wait_for(state="hidden")
        self.page.locator(".collection-content").wait_for(state="visible")
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.locator("#delete").click()
        self.page.wait_for_url("**/my/collections", wait_until="domcontentloaded")

    def publish(self):
        """Click the Publish button and wait for the success page."""
        self.page.locator("#publish").click()
        # The JS saves first, then POSTs to /publish, then does
        # window.location.replace("/my/collections/published/<id>")
        self.page.wait_for_url(
            "**/my/collections/published/**",
            wait_until="domcontentloaded",
            timeout=60000,
        )

    def is_save_visible(self) -> bool:
        return self.page.locator("#save").is_visible()

    def is_delete_visible(self) -> bool:
        return self.page.locator("#delete").is_visible()

    def is_publish_visible(self) -> bool:
        return self.page.locator("#publish").is_visible()

    @property
    def heading(self) -> str:
        return self.page.locator(".collection-content h1").inner_text()

    @property
    def container_uuid(self) -> str:
        """Extract the container UUID from the current page URL."""
        if self._container_uuid is None:
            match = re.search(r"/my/collections/([^/]+)/edit", self.page.url)
            if match:
                self._container_uuid = match.group(1)
        return self._container_uuid

    def get_dataset_count(self) -> int:
        """Return the number of datasets listed in the collection."""
        table = self.page.locator("#articles-list")
        if not table.is_visible():
            return 0
        return self.page.locator("#articles-list tbody tr").count()

    def get_dataset_names(self) -> list[str]:
        """Return list of dataset titles shown in the articles list."""
        rows = self.page.locator("#articles-list tbody tr")
        names = []
        for i in range(rows.count()):
            cell = rows.nth(i).locator("td:first-child a")
            names.append(cell.inner_text())
        return names
