"""
Page object for the admin license-change page
(/admin/update-published-dataset/license).

The page is a three-step flow:
    Step 1 - Search and select a published dataset.
    Step 2 - Review the current license and pick a replacement.
    Step 3 - Review the diff (with a legal-implications warning) and confirm.
"""

from playwright.sync_api import expect

from pages.base_page import BasePage


class AdminLicensePage(BasePage):
    """Interact with the admin license-change page."""

    PATH = "/admin/update-published-dataset/license"

    def navigate(self, path: str = PATH):
        super().navigate(path)
        self.page.locator("#license-search-input").wait_for(state="visible")

    # Step 1 ------------------------------------------------------------

    def search(self, query: str):
        self.page.locator("#license-search-input").fill(query)
        self.page.locator("#license-search-button").click()

    def wait_for_results(self):
        self.page.locator("#license-results").wait_for(state="visible")

    def result_rows(self):
        return self.page.locator("#license-results-body tr")

    def row_for_title(self, title: str):
        return self.result_rows().filter(has_text=title)

    def select_row_by_title(self, title: str):
        self.row_for_title(title).first.click()
        expect(self.page.locator("#license-step-2")).to_be_visible()

    # Step 2 ------------------------------------------------------------

    def detail_value(self, field: str) -> str:
        """Read the text of a Step 2 detail field (title, doi, version,
        current-name, current-url, container-uri, dataset-uri)."""
        return self.page.locator(f"#license-detail-{field}").inner_text()

    def select_license(self, url: str):
        self.page.locator("#license-select").select_option(value=url)

    def click_change_dataset(self):
        self.page.locator("#license-back-to-search-button").click()
        expect(self.page.locator("#license-step-1")).to_be_visible()

    def click_preview(self):
        self.page.locator("#license-preview-button").click()
        expect(self.page.locator("#license-step-3")).to_be_visible()

    # Step 3 ------------------------------------------------------------

    def confirm_value(self, field: str) -> str:
        """Read the text of a Step 3 confirm field (title, doi, version,
        from-name, from-url, to-name, to-url)."""
        return self.page.locator(f"#license-confirm-{field}").inner_text()

    def warning_visible(self) -> bool:
        return self.page.locator(".license-warning").is_visible()

    def click_back(self):
        self.page.locator("#license-back-to-pick-button").click()
        expect(self.page.locator("#license-step-2")).to_be_visible()

    def click_confirm(self):
        self.page.locator("#license-confirm-button").click()
