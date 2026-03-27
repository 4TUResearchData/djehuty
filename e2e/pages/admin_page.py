"""
Page object for the admin panel (/admin/*).
"""

from pages.base_page import BasePage


class AdminPage(BasePage):
    """Interact with the admin panel."""

    PATH = "/admin/dashboard"

    def navigate(self, path: str = PATH):
        super().navigate(path)

    def open_users(self):
        self.page.locator("a[href='/admin/users']").click()
        self.page.wait_for_load_state("domcontentloaded")

    def open_maintenance(self):
        self.page.locator("a[href='/admin/maintenance']").click()
        self.page.wait_for_load_state("domcontentloaded")

    def impersonate_user(self, email: str):
        """Navigate to the impersonation flow for a given user email.

        This relies on the admin having ``may-impersonate`` privileges and
        the admin panel exposing an impersonation action.
        """
        self.open_users()
        self.page.get_by_text(email).click()
        self.page.get_by_role("button", name="Impersonate").click()
        self.page.wait_for_load_state("domcontentloaded")
