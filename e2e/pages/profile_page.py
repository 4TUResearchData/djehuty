"""
Page object for the user profile page (/my/profile).
"""

from pages.base_page import BasePage


class ProfilePage(BasePage):
    """Interact with the user profile editing form."""

    PATH = "/my/profile"

    def navigate(self, path: str = PATH):
        super().navigate(path)
        # Wait for JS to initialize (activate function binds handlers)
        self.page.locator("#save").wait_for(state="visible")

    def get_first_name(self) -> str:
        return self.page.locator("#first_name").input_value()

    def set_first_name(self, value: str):
        self.page.locator("#first_name").fill(value)

    def get_last_name(self) -> str:
        return self.page.locator("#last_name").input_value()

    def set_last_name(self, value: str):
        self.page.locator("#last_name").fill(value)

    def get_job_title(self) -> str:
        return self.page.locator("#job_title").input_value()

    def set_job_title(self, value: str):
        self.page.locator("#job_title").fill(value)

    def get_location(self) -> str:
        return self.page.locator("#location").input_value()

    def set_location(self, value: str):
        self.page.locator("#location").fill(value)

    def get_twitter(self) -> str:
        return self.page.locator("#twitter").input_value()

    def set_twitter(self, value: str):
        self.page.locator("#twitter").fill(value)

    def get_linkedin(self) -> str:
        return self.page.locator("#linkedin").input_value()

    def set_linkedin(self, value: str):
        self.page.locator("#linkedin").fill(value)

    def get_website(self) -> str:
        return self.page.locator("#website").input_value()

    def set_website(self, value: str):
        self.page.locator("#website").fill(value)

    def get_biography(self) -> str:
        return self.page.locator("#biography").input_value()

    def set_biography(self, value: str):
        self.page.locator("#biography").fill(value)

    def save(self):
        self.page.locator("#save").click()
        self.page.locator("#message.success").wait_for(state="visible")

    def is_save_visible(self) -> bool:
        return self.page.locator("#save").is_visible()

    def expand_categories(self):
        self.page.locator("#expand-categories-button").click()
        self.page.locator("#expanded-categories").wait_for(state="visible")

    def is_categories_visible(self) -> bool:
        return self.page.locator("#expanded-categories").is_visible()
