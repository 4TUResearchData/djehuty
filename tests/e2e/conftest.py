"""
Shared fixtures for Playwright E2E tests.

Provides:
    - browser_context:      Fresh browser context per test
    - page:                 Fresh page per test (overrides pytest-playwright default)
    - authenticated_page:   Page with an active session (auto-login)
    - admin_page:           Authenticated page with admin privileges
    - screenshot:           Callable to capture numbered screenshots
"""

from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext, Page
from slugify import slugify

from config import BASE_URL, TIMEOUT
from helpers.api_response import ApiResponseHelper
from helpers.screenshot import ScreenshotHelper


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
# Screenshots
# ---------------------------------------------------------------------------

@pytest.fixture()
def screenshot(pytestconfig, request):
    """Provide a callable that saves numbered screenshots for the current test.

    Usage::

        def test_example(self, page, screenshot):
            page.goto("/portal")
            screenshot(page, "portal-loaded")

    Screenshots are saved as ``<output>/<test-name>/<index>-<description>.png``.
    """
    output_dir = Path(pytestconfig.getoption("--output")).absolute()
    test_name = slugify(request.node.nodeid)
    return ScreenshotHelper(output_dir / test_name)


@pytest.fixture()
def save_response(pytestconfig, request):
    """Provide a callable that saves numbered API JSON responses for the current test.

    Usage::

        def test_example(self, page, save_response):
            response = page.request.get("/v2/articles")
            save_response(response, "list-articles")

    Responses are saved as ``<output>/<test-name>/<index>-<description>.json``.
    """
    output_dir = Path(pytestconfig.getoption("--output")).absolute()
    test_name = slugify(request.node.nodeid)
    return ApiResponseHelper(output_dir / test_name)


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


@pytest.fixture()
def created_collection(authenticated_page: Page):
    """Create a draft collection via the UI and return its URL.

    Tears down by deleting the collection after the test.
    """
    from helpers.collection import create_draft_collection, delete_collection

    collection_url = create_draft_collection(authenticated_page)
    yield collection_url
    delete_collection(authenticated_page, collection_url)
