"""
Dataset helper utilities for E2E tests.
"""

import re

from pages.dataset_editor_page import DatasetEditorPage
from playwright.sync_api import Page


def create_draft_dataset(page: Page) -> str:
    """Create a new draft dataset via the UI and return its edit URL.

    Assumes the page is already authenticated.
    """
    page.goto("/my/datasets/new")
    page.wait_for_load_state("domcontentloaded")
    # The redirect lands on /my/datasets/<container_uuid>/edit
    page.wait_for_url("**/my/datasets/*/edit")
    # Wait for JS to initialize the form
    page.locator(".article-content").wait_for(state="visible")
    return page.url


def get_container_uuid_from_url(url: str) -> str:
    """Extract the container UUID from a dataset editor URL."""
    match = re.search(r"/my/datasets/([^/]+)/edit", url)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot extract container UUID from: {url}")


def delete_dataset(page: Page, dataset_url: str):
    """Soft-delete a dataset identified by its editor URL."""
    page.goto(dataset_url)
    DatasetEditorPage(page).delete()


def get_dataset_uuid_from_editor(page: Page) -> str:
    """Extract the dataset UUID from the private links button on the editor page.

    The editor page must be loaded before calling this.
    """
    href = page.locator("#private-links").get_attribute("href")
    match = re.search(r"/my/datasets/([^/]+)/private_links", href)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot extract dataset UUID from href: {href}")


def upload_file(page: Page, file_path: str):
    """Upload a file to the current dataset editor page via Dropzone."""
    page.locator("form#dropzone-field").wait_for(state="visible")
    with page.expect_file_chooser() as fc_info:
        page.locator("form#dropzone-field").click()
    fc_info.value.set_files(file_path)
    page.locator("table#files tbody tr").first.wait_for(state="visible")
