"""
Page object for the dataset editor (/my/datasets/<id>/edit).
"""

from playwright.sync_api import Page, expect

from pages.base_page import BasePage


class DatasetEditorPage(BasePage):
    """Interact with the dataset creation / editing form."""

    def __init__(self, page: Page):
        super().__init__(page)

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
