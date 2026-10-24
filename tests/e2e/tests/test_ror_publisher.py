"""
ROR publisher link tests.
"""

from pathlib import Path

import pytest
from helpers.dataset import create_draft_dataset, get_container_uuid_from_url
from helpers.publish import fill_required_fields_and_publish
from pages.dataset_editor_page import DatasetEditorPage
from playwright.sync_api import Page, expect

TEST_FILE_CONTENT = b"ROR publisher test file.\n"
TEST_FILE_NAME = "ror-test-file.txt"
ROR_URL = "https://ror.org/02d887280"


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    file_path = tmp_path / TEST_FILE_NAME
    file_path.write_bytes(TEST_FILE_CONTENT)
    return str(file_path)


@pytest.fixture()
def published_dataset(authenticated_page: Page, test_file: str):
    """Create, publish a dataset."""
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(test_file)
    editor.save()

    fill_required_fields_and_publish(
        authenticated_page,
        container_uuid,
        title="ROR Publisher Test Dataset",
        description="<p>Dataset for verifying the ROR publisher link.</p>",
    )

    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")

    for _ in range(5):
        authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        if authenticated_page.locator("#publisher").count() > 0:
            break
        authenticated_page.wait_for_timeout(3000)

    return authenticated_page, container_uuid


@pytest.mark.dataset
class TestRorPublisherLink:
    """Verify the publisher name is plain text and only the ROR icon links."""

    def test_ror_icon_opens_ror_record(self, published_dataset, screenshot):
        """Clicking the ROR icon should open the ROR record in a new tab."""
        page, _ = published_dataset
        page.context.route(f"{ROR_URL}**", lambda route: route.fulfill(body="ok"))
        screenshot(page, "dataset-publisher")

        with page.context.expect_page() as popup_info:
            page.locator("#publisher a img.ror-icon").click()
        popup = popup_info.value
        popup.wait_for_load_state()
        assert popup.url.startswith(ROR_URL)

    def test_publisher_name_is_not_a_link(self, published_dataset):
        """The publisher name must render as plain text, not inside the ROR link."""
        page, _ = published_dataset
        expect(page.locator("#publisher")).to_contain_text("4TU.ResearchData")
        expect(page.locator("#publisher a", has_text="4TU.ResearchData")).to_have_count(0)

    def test_ror_icon_asset_served(self, page: Page):
        """The ROR icon SVG should be reachable as a static asset."""
        response = page.request.get("/static/images/ror-icon.svg")
        assert response.ok
        assert "svg" in response.headers.get("content-type", "").lower()
