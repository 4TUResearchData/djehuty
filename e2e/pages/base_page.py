"""
Base page object that all page objects inherit from.
"""

from playwright.sync_api import Page


class BasePage:
    """Common helpers shared by every page object."""

    def __init__(self, page: Page):
        self.page = page

    def navigate(self, path: str = "/"):
        self.page.goto(path)
        self.page.wait_for_load_state("domcontentloaded")

    @property
    def title(self) -> str:
        return self.page.title()

    def get_text(self, selector: str) -> str:
        return self.page.locator(selector).inner_text()

    def click(self, selector: str):
        self.page.locator(selector).click()

    def fill(self, selector: str, value: str):
        self.page.locator(selector).fill(value)
