"""
Impersonation helper for testing access control as different roles/users.

Requires the current session to have ``may-impersonate`` privileges
(the default dev account does).
"""

from playwright.sync_api import Page


def impersonate(page: Page, account_uuid: str):
    """Switch to another user via the admin impersonation endpoint.

    After calling this the browser session acts as the impersonated user.
    The ``account_uuid`` must be the UUID of an existing account.
    """
    page.goto(f"/admin/impersonate/{account_uuid}")
    page.wait_for_load_state("domcontentloaded")


def stop_impersonation(page: Page):
    """Return to the original admin session by logging out of impersonation.

    When impersonating, /logout restores the original admin session
    instead of fully logging out.
    """
    page.goto("/logout")
    page.wait_for_load_state("domcontentloaded")
