"""
Page object for the admin remove-files page
(/admin/update-published-dataset/remove-files).

A four-step flow:
    Step 1 - Search and select a published dataset.
    Step 2 - Pick the version to remove files from.
    Step 3 - Tick the files to remove.
    Step 4 - Type the DOI to enable Remove, then remove.
"""

from playwright.sync_api import expect

from pages.base_page import BasePage


class AdminRemoveFilesPage(BasePage):
    """Interact with the admin remove-files page."""

    PATH = "/admin/update-published-dataset/remove-files"

    def navigate(self, path: str = PATH):
        super().navigate(path)
        self.page.locator("#rmf-search-input").wait_for(state="visible")

    # Step 1 ------------------------------------------------------------

    def search(self, query: str):
        self.page.locator("#rmf-search-input").fill(query)
        self.page.locator("#rmf-search-button").click()

    def wait_for_results(self):
        self.page.locator("#rmf-results").wait_for(state="visible")

    def result_rows(self):
        return self.page.locator("#rmf-results-body tr")

    def row_for_title(self, title: str):
        return self.result_rows().filter(has_text=title)

    def select_dataset_by_title(self, title: str):
        self.row_for_title(title).first.click()
        expect(self.page.locator("#rmf-step-2")).to_be_visible()

    # Step 2 ------------------------------------------------------------

    def version_rows(self):
        return self.page.locator("#rmf-versions-body tr")

    def select_first_version(self):
        self.version_rows().first.click()
        expect(self.page.locator("#rmf-step-3")).to_be_visible()

    def click_change_dataset(self):
        self.page.locator("#rmf-back-to-search-button").click()
        expect(self.page.locator("#rmf-step-1")).to_be_visible()

    # Step 3 ------------------------------------------------------------

    def file_rows(self):
        return self.page.locator("#rmf-files-body tr")

    def file_checkboxes(self):
        return self.page.locator("#rmf-files-body input.rmf-file-checkbox")

    def select_file_by_name(self, name: str):
        self.file_rows().filter(has_text=name).locator("input.rmf-file-checkbox").check()

    def toggle_select_all(self):
        self.page.locator("#rmf-select-all").check()

    def continue_button(self):
        return self.page.locator("#rmf-continue-button")

    def click_continue(self):
        self.continue_button().click()
        expect(self.page.locator("#rmf-step-4")).to_be_visible()

    def click_change_version(self):
        self.page.locator("#rmf-back-to-versions-button").click()
        expect(self.page.locator("#rmf-step-2")).to_be_visible()

    # Step 4 ------------------------------------------------------------

    def confirm_value(self, field: str) -> str:
        """Read a Step 4 confirm field (title, version, doi)."""
        return self.page.locator(f"#rmf-confirm-{field}").inner_text()

    def confirm_file_names(self) -> list:
        return self.page.locator("#rmf-confirm-file-list li").all_inner_texts()

    def type_doi_confirmation(self, doi: str):
        self.page.locator("#rmf-doi-confirm-input").fill(doi)

    def confirm_button(self):
        return self.page.locator("#rmf-confirm-button")

    def click_back_to_files(self):
        self.page.locator("#rmf-back-to-files-button").click()
        expect(self.page.locator("#rmf-step-3")).to_be_visible()

    def click_confirm(self):
        self.confirm_button().click()
