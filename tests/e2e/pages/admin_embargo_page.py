"""
Page object for the admin embargo management page
(/admin/update-published-dataset/embargos).

The page is a three-step flow:
    Step 1 - Search and select a dataset.
    Step 2 - Review the selected dataset and set a new embargo date.
    Step 3 - Preview the change and confirm.
"""

from playwright.sync_api import expect

from pages.base_page import BasePage


class AdminEmbargoPage(BasePage):
    """Interact with the admin embargo management page."""

    PATH = "/admin/update-published-dataset/embargos"

    def navigate(self, path: str = PATH):
        super().navigate(path)
        self.page.locator("#embargo-search-input").wait_for(state="visible")

    # ------------------------------------------------------------------
    # Step 1 - search & select
    # ------------------------------------------------------------------

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
        """Click a search result; the page advances to Step 2."""
        self.row_for_title(title).first.click()
        expect(self.page.locator("#embargo-step-2")).to_be_visible()

    # ------------------------------------------------------------------
    # Step 2 - edit
    # ------------------------------------------------------------------

    def detail_value(self, field: str) -> str:
        """Read the text of a Step 2 detail field (title, doi, embargo-type,
        embargo-title, embargo-reason, embargo-date)."""
        return self.page.locator(f"#detail-{field}").inner_text()

    def set_embargo_date(self, iso_date: str):
        self.page.locator("#embargo-date-input").fill(iso_date)

    def click_change_dataset(self):
        """Go back to Step 1 to pick a different dataset."""
        self.page.locator("#embargo-back-to-search-button").click()
        expect(self.page.locator("#embargo-step-1")).to_be_visible()

    def click_preview(self):
        """Advance from Step 2 to Step 3 (preview & confirm)."""
        self.page.locator("#embargo-preview-button").click()
        expect(self.page.locator("#embargo-step-3")).to_be_visible()

    # ------------------------------------------------------------------
    # Step 3 - preview & confirm
    # ------------------------------------------------------------------

    def confirm_value(self, field: str) -> str:
        """Read the text of a Step 3 confirm field (title, doi,
        embargo-type, from-date, to-date)."""
        return self.page.locator(f"#confirm-{field}").inner_text()

    def click_back_to_edit(self):
        self.page.locator("#embargo-back-to-edit-button").click()
        expect(self.page.locator("#embargo-step-2")).to_be_visible()

    def click_confirm(self):
        self.page.locator("#embargo-confirm-button").click()
