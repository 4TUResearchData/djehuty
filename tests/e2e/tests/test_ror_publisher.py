"""
ROR publisher link tests.

Covers:
    - The publisher block on a published dataset links to the configured
      ROR URL with the ROR icon when item.publisher matches site_name.
    - The ROR icon SVG is served from /static/images/ror-icon.svg.

Run with:
    cd tests/e2e && python -m pytest tests/test_ror_publisher.py -v
"""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from helpers.dataset import create_draft_dataset, get_container_uuid_from_url
from helpers.publish import fill_required_fields_and_publish
from pages.dataset_editor_page import DatasetEditorPage


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
    """Create, publish a dataset (publisher defaults to 4TU.ResearchData)."""
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

    # The SPARQL store may need a moment to reflect the published state.
    for _ in range(5):
        authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        if authenticated_page.locator("#publisher").count() > 0:
            break
        authenticated_page.wait_for_timeout(3000)

    return authenticated_page, container_uuid


@pytest.mark.ror
class TestRorPublisherLink:
    """Verify the ROR link and icon render in the publisher block."""

    def test_publisher_links_to_ror_with_icon(self, published_dataset, screenshot):
        """Publisher should be a link to the ROR URL with the ROR icon adjacent."""
        page, _ = published_dataset
        screenshot(page, "dataset-publisher")

        link = page.locator(f"#publisher a[href='{ROR_URL}']")
        expect(link).to_be_visible()
        expect(link).to_contain_text("4TU.ResearchData")
        expect(link.locator("img.ror-icon")).to_be_visible()

    def test_ror_icon_asset_served(self, page: Page):
        """The ROR icon SVG should be reachable as a static asset."""
        response = page.request.get("/static/images/ror-icon.svg")
        assert response.ok
        assert "svg" in response.headers.get("content-type", "").lower()
