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

    def open_reports(self):
        self.page.locator("a[href='/admin/reports']").click()
        self.page.wait_for_load_state("domcontentloaded")

    def open_quota_requests(self):
        self.page.locator("a[href='/admin/quota-requests']").click()
        self.page.wait_for_load_state("domcontentloaded")

    def open_maintenance(self):
        self.page.locator("a[href='/admin/maintenance']").click()
        self.page.wait_for_load_state("domcontentloaded")

    def impersonate_user(self, account_uuid: str):
        """Impersonate a user by navigating to /admin/impersonate/<uuid>.

        This relies on the admin having ``may-impersonate`` privileges.
        After impersonation the browser is redirected to /my/dashboard
        as the impersonated user.
        """
        self.page.goto(f"/admin/impersonate/{account_uuid}")
        self.page.wait_for_load_state("domcontentloaded")
