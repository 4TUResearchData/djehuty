"""
Page object for the dataset editor.
"""

from pages.base_page import BasePage


class DatasetEditorPage(BasePage):
    """Interact with the dataset creation / editing form."""

    def set_title(self, title: str):
        self.fill("input[name='title']", title)

    def set_description(self, description: str):
        # The description field may be a textarea or a rich-text editor.
        self.page.locator("textarea[name='description']").fill(description)

    def save(self):
        self.page.get_by_role("button", name="Save").click()
        self.page.wait_for_load_state("networkidle")
