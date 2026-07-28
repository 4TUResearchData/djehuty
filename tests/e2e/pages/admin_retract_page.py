"""
Page object for the admin retract page
(/admin/update-published-dataset/retract).

The page is a three-step flow:
    Step 1 - Search and select a published dataset.
    Step 2 - Review the selected target.
    Step 3 - Type the DOI to enable Confirm, then retract.
"""

from playwright.sync_api import expect

from pages.base_page import BasePage


class AdminRetractPage(BasePage):
    """Interact with the admin retract page."""

    PATH = "/admin/update-published-dataset/retract"

    def navigate(self, path: str = PATH):
        super().navigate(path)
        self.page.locator("#retract-search-input").wait_for(state="visible")

    # Step 1 ------------------------------------------------------------

    def search(self, query: str):
        self.page.locator("#retract-search-input").fill(query)
        self.page.locator("#retract-search-button").click()

    def wait_for_results(self):
        self.page.locator("#retract-results").wait_for(state="visible")

    def result_rows(self):
        return self.page.locator("#retract-results-body tr")

    def row_for_title(self, title: str):
        return self.result_rows().filter(has_text=title)

    def select_row_by_title(self, title: str):
        self.row_for_title(title).first.click()
        expect(self.page.locator("#retract-step-2")).to_be_visible()

    # Step 2 ------------------------------------------------------------

    def detail_value(self, field: str) -> str:
        """Read the text of a Step 2 detail field (title, doi, version,
        published, container-uuid, dataset-uuid)."""
        return self.page.locator(f"#retract-detail-{field}").inner_text()

    def click_change_dataset(self):
        self.page.locator("#retract-back-to-search-button").click()
        expect(self.page.locator("#retract-step-1")).to_be_visible()

    def click_preview(self):
        self.page.locator("#retract-preview-button").click()
        expect(self.page.locator("#retract-step-3")).to_be_visible()

    # Step 3 ------------------------------------------------------------

    def confirm_value(self, field: str) -> str:
        """Read the text of a Step 3 confirm field (title, doi, version)."""
        return self.page.locator(f"#retract-confirm-{field}").inner_text()

    def type_doi_confirmation(self, doi: str):
        self.page.locator("#retract-doi-confirm-input").fill(doi)

    def confirm_button(self):
        return self.page.locator("#retract-confirm-button")

    def click_back(self):
        self.page.locator("#retract-back-to-detail-button").click()
        expect(self.page.locator("#retract-step-2")).to_be_visible()

    def click_confirm(self):
        self.confirm_button().click()
