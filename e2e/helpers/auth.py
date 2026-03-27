"""
Authentication helpers for E2E tests.
"""

from playwright.sync_api import Page


def login(page: Page):
    """Perform automatic login via the dev auto-login flow.

    Navigates to /login and waits for the redirect to the dashboard,
    which confirms that the session cookie has been set.
    """
    page.goto("/login")
    page.wait_for_url("**/my/dashboard**")


def is_logged_in(page: Page) -> bool:
    """Check whether the current page has an active session."""
    page.goto("/my/dashboard")
    return "/my/dashboard" in page.url
