"""
Page object for the /search page.
"""

from playwright.sync_api import Page

from pages.base_page import BasePage


class SearchPage(BasePage):
    """Interact with the search results page at /search."""

    SEARCH_INPUT = "#search-box"
    SEARCH_SUBMIT = ".search-submit-btn"
    SORT_SELECT = "#sort-by"
    TILE_VIEW_MODE = "#tile-view-mode"
    LIST_VIEW_MODE = "#list-view-mode"
    TILE_RESULTS = "#search-results-tile-view"
    LIST_RESULTS = "#search-results-list-view"
    RESULT_COUNT = "#search-results-count"
    LOADER = "#search-loader"
    ERROR = "#search-error"
    PAGER = ".search-results-pager"
    FILTER_APPLY = "#search-filter-apply-button"
    FILTER_RESET = "#search-filter-reset-button"

    def __init__(self, page: Page):
        super().__init__(page)

    def navigate(self, path: str = "/search"):
        super().navigate(path)

    def search_from_header(self, query: str):
        """Type a query in the header search bar and submit."""
        self.page.locator(self.SEARCH_INPUT).fill(query)
        self.page.locator(self.SEARCH_SUBMIT).click()
        self.page.wait_for_load_state("domcontentloaded")

    def wait_for_results(self, timeout: int = 15000):
        """Wait until the search loader disappears and results appear."""
        self.page.locator(self.LOADER).wait_for(state="hidden", timeout=timeout)
        # Wait for either tile or list results to have content, or error
        self.page.wait_for_function(
            """() => {
                const tile = document.querySelector('#search-results-tile-view');
                const error = document.querySelector('#search-error');
                return (tile && tile.children.length > 0) ||
                       (error && error.style.display !== 'none' && error.textContent !== '');
            }""",
            timeout=timeout,
        )

    def get_result_count_text(self) -> str:
        return self.page.locator(self.RESULT_COUNT).inner_text()

    def get_tile_items(self):
        return self.page.locator(f"{self.TILE_RESULTS} .tile-item")

    def get_tile_count(self) -> int:
        return self.get_tile_items().count()

    def switch_to_list_view(self):
        self.page.locator(self.LIST_VIEW_MODE).click()

    def switch_to_tile_view(self):
        self.page.locator(self.TILE_VIEW_MODE).click()

    def is_list_view_visible(self) -> bool:
        return self.page.locator(self.LIST_RESULTS).is_visible()

    def select_sort(self, value: str):
        """Select a sort option by value (date_asc, date_dsc, title_asc, title_dsc)."""
        self.page.locator(self.SORT_SELECT).select_option(value)

    def apply_filters(self):
        self.page.locator(self.FILTER_APPLY).click()

    def reset_filters(self):
        self.page.locator(self.FILTER_RESET).click()

    def check_filter(self, checkbox_id: str):
        """Check a filter checkbox by its ID (without #)."""
        self.page.locator(f"#{checkbox_id}").check()

    def get_pager(self):
        return self.page.locator(self.PAGER)

    def has_pager(self) -> bool:
        return self.get_pager().locator("div").count() > 0
