"""
Page object for the depositor dashboard (/my/dashboard).
"""

from pages.base_page import BasePage


class DashboardPage(BasePage):
    """Interact with the depositor dashboard."""

    PATH = "/my/dashboard"

    def navigate(self, path: str = PATH):
        super().navigate(path)

    def open_datasets(self):
        self.page.locator("a[href='/my/datasets']").click()
        self.page.wait_for_load_state("domcontentloaded")

    def open_collections(self):
        self.page.locator("a[href='/my/collections']").click()
        self.page.wait_for_load_state("domcontentloaded")
