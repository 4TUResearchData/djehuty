"""
Page object for the admin embargo management page
(/admin/update-published-dataset/embargos).
"""

from playwright.sync_api import expect

from pages.base_page import BasePage


class AdminEmbargoPage(BasePage):
    """Interact with the admin embargo management page."""

    PATH = "/admin/update-published-dataset/embargos"

    def navigate(self, path: str = PATH):
        super().navigate(path)
        self.page.locator("#embargo-search-input").wait_for(state="visible")

    def search(self, query: str):
        self.page.locator("#embargo-search-input").fill(query)
        self.page.locator("#embargo-search-button").click()

    def wait_for_results(self):
        self.page.locator("#embargo-results").wait_for(state="visible")

    def result_rows(self):
        return self.page.locator("#embargo-results-body tr")

    def row_for_title(self, title: str):
        return self.result_rows().filter(has_text=title)

    def select_row_by_title(self, title: str):
        self.row_for_title(title).first.click()
        expect(self.page.locator("#embargo-detail")).to_be_visible()

    def set_embargo_date(self, iso_date: str):
        self.page.locator("#embargo-date-input").fill(iso_date)

    def click_update(self):
        self.page.locator("#embargo-update-button").click()

    def detail_value(self, field: str) -> str:
        """Read the text of a detail field (title, doi, embargo-type,
        embargo-title, embargo-reason, embargo-date)."""
        return self.page.locator(f"#detail-{field}").inner_text()
