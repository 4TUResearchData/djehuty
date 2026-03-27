"""
Impersonation helper for testing access control as different roles/users.

Requires the current session to have ``may-impersonate`` privileges
(the default dev account does).
"""

from playwright.sync_api import Page


def impersonate(page: Page, email: str):
    """Switch to another user via the admin impersonation endpoint.

    After calling this the browser session acts as ``email``.
    """
    page.goto(f"/admin/impersonate?email={email}")
    page.wait_for_load_state("domcontentloaded")


def stop_impersonation(page: Page):
    """Return to the original admin session."""
    page.goto("/admin/impersonate/stop")
    page.wait_for_load_state("domcontentloaded")
