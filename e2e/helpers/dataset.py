"""
Dataset helper utilities for E2E tests.
"""

from playwright.sync_api import Page


def create_draft_dataset(page: Page) -> str:
    """Create a new draft dataset via the UI and return its URL.

    Assumes the page is already authenticated.
    """
    page.goto("/my/datasets")
    page.get_by_role("button", name="Create new dataset").click()
    page.wait_for_load_state("domcontentloaded")
    return page.url


def delete_dataset(page: Page, dataset_url: str):
    """Delete a dataset identified by its editor URL.

    Uses the delete action available on the dataset editor page.
    """
    page.goto(dataset_url)
    page.get_by_role("button", name="Delete").click()
    # Confirm deletion dialog if present.
    confirm = page.get_by_role("button", name="Confirm")
    if confirm.is_visible():
        confirm.click()
    page.wait_for_load_state("domcontentloaded")


def upload_file(page: Page, file_path: str):
    """Upload a file to the current dataset editor page."""
    page.locator("input[type='file']").set_input_files(file_path)
    page.wait_for_load_state("networkidle")
