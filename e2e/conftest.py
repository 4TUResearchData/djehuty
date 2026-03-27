"""
Shared fixtures for Playwright E2E tests.

Provides:
    - browser_context:      Fresh browser context per test
    - page:                 Fresh page per test (overrides pytest-playwright default)
    - authenticated_page:   Page with an active session (auto-login)
    - admin_page:           Authenticated page with admin privileges
"""

import pytest
from playwright.sync_api import BrowserContext, Page

from config import BASE_URL, TIMEOUT


# ---------------------------------------------------------------------------
# Browser context
# ---------------------------------------------------------------------------

@pytest.fixture()
def browser_context(browser):
    """Yield an isolated browser context and close it after the test."""
    context = browser.new_context(
        base_url=BASE_URL,
        viewport={"width": 1280, "height": 720},
    )
    context.set_default_timeout(TIMEOUT)
    yield context
    context.close()


@pytest.fixture()
def page(browser_context: BrowserContext):
    """Yield a fresh page inside the browser context."""
    pg = browser_context.new_page()
    yield pg
    pg.close()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@pytest.fixture()
def authenticated_page(page: Page):
    """Return a page that has gone through the automatic login flow.

    The dev configuration uses ``<automatic-login-email>`` so visiting
    ``/login`` immediately creates a session cookie.
    """
    page.goto("/login")
    # After auto-login, the app redirects to the depositor dashboard.
    page.wait_for_url("**/my/dashboard**")
    return page


@pytest.fixture()
def admin_page(authenticated_page: Page):
    """Return an authenticated page and verify admin access.

    The default dev account (dev@djehuty.com) has admin privileges.
    """
    authenticated_page.goto("/admin/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")
    return authenticated_page


# ---------------------------------------------------------------------------
# Test-data helpers (setup / teardown)
# ---------------------------------------------------------------------------

@pytest.fixture()
def created_dataset(authenticated_page: Page):
    """Create a draft dataset via the UI and return its URL.

    Tears down by deleting the dataset after the test.
    """
    from helpers.dataset import create_draft_dataset, delete_dataset

    dataset_url = create_draft_dataset(authenticated_page)
    yield dataset_url
    delete_dataset(authenticated_page, dataset_url)
