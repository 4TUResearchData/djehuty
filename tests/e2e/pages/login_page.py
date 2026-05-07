"""
Page object for the login page.
"""

from pages.base_page import BasePage


class LoginPage(BasePage):
    """Interact with /login."""

    PATH = "/login"

    def navigate(self, path: str = PATH):
        super().navigate(path)

    def login_auto(self):
        """Trigger automatic login (dev environment only).

        With ``<automatic-login-email>`` configured, visiting /login
        immediately creates a session and redirects to the dashboard.
        """
        self.navigate()
        self.page.wait_for_url("**/my/dashboard**")
