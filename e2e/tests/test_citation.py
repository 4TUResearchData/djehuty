"""
Citation & export tests.

Covers:
    - Open cite dialog on a published dataset page
    - Verify all export format links are present
    - Download each export format and verify non-empty response

Run with:
    cd e2e && python -m pytest tests/test_citation.py -v
"""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from helpers.dataset import create_draft_dataset, get_container_uuid_from_url
from helpers.publish import fill_required_fields_and_publish
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_FILE_CONTENT = b"Citation export test file.\n"
TEST_FILE_NAME = "citation-test-file.txt"

EXPORT_FORMATS = [
    ("refworks", "RefWorks"),
    ("bibtex", "BibTeX"),
    ("refman", "Reference Manager"),
    ("endnote", "Endnote"),
    ("datacite", "DataCite"),
    ("nlm", "NLM"),
    ("dc", "DC"),
    ("cff", "CFF"),
]


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    """Create a temporary test file and return its path."""
    file_path = tmp_path / TEST_FILE_NAME
    file_path.write_bytes(TEST_FILE_CONTENT)
    return str(file_path)


@pytest.fixture()
def published_dataset(authenticated_page: Page, test_file: str):
    """Create, publish a dataset, and return (page, container_uuid)."""
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(test_file)
    editor.save()

    fill_required_fields_and_publish(
        authenticated_page,
        container_uuid,
        title="Citation Export Test Dataset",
        description="<p>Dataset for testing citation and export features.</p>",
    )

    # Re-login after publish (review flow logs out)
    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")

    # Wait for the published dataset to be visible on the public page.
    # The SPARQL store may need a moment to reflect the published state.
    for _ in range(5):
        authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        if authenticated_page.locator("#export").count() > 0:
            break
        authenticated_page.wait_for_timeout(3000)

    return authenticated_page, container_uuid


# ---------------------------------------------------------------------------
# Cite dialog tests
# ---------------------------------------------------------------------------


@pytest.mark.citation
class TestCiteDialog:
    """Test the citation dialog on a published dataset page."""

    def test_cite_button_visible(self, published_dataset, screenshot):
        """The Cite button should be visible on a published dataset page."""
        page, container_uuid = published_dataset
        page.goto(f"/datasets/{container_uuid}")
        page.wait_for_load_state("domcontentloaded")
        screenshot(page, "dataset-page-loaded")

        expect(page.locator("#cite-btn")).to_be_visible()

    def test_cite_dialog_opens_on_click(self, published_dataset, screenshot):
        """Clicking Cite should reveal the citation section."""
        page, container_uuid = published_dataset
        page.goto(f"/datasets/{container_uuid}")
        page.wait_for_load_state("domcontentloaded")

        # Citation section should be hidden initially
        expect(page.locator("#cite")).to_be_hidden()

        # Click the Cite button
        page.locator("#cite-btn").click()
        expect(page.locator("#cite")).to_be_visible()
        screenshot(page, "cite-dialog-open")

        # Citation text should be non-empty
        citation_text = page.locator("#citation").inner_text()
        assert len(citation_text.strip()) > 0, "Citation text should not be empty"

    def test_cite_dialog_toggles(self, published_dataset, screenshot):
        """Clicking Cite twice should hide the citation section again."""
        page, container_uuid = published_dataset
        page.goto(f"/datasets/{container_uuid}")
        page.wait_for_load_state("domcontentloaded")

        # Open
        page.locator("#cite-btn").click()
        expect(page.locator("#cite")).to_be_visible()
        screenshot(page, "cite-open")

        # Close
        page.locator("#cite-btn").click()
        expect(page.locator("#cite")).to_be_hidden()
        screenshot(page, "cite-closed")


# ---------------------------------------------------------------------------
# Export link tests
# ---------------------------------------------------------------------------


@pytest.mark.citation
class TestExportLinks:
    """Test that all export format links are present on a published dataset page."""

    def test_export_section_visible(self, published_dataset, screenshot):
        """The export section should be visible on a published dataset page."""
        page, container_uuid = published_dataset
        page.goto(f"/datasets/{container_uuid}")
        page.wait_for_load_state("domcontentloaded")
        page.locator("#metadata").wait_for(state="visible")
        screenshot(page, "export-section")

        expect(page.locator("#export")).to_be_visible()
        expect(page.locator("#export h3")).to_have_text("Export as...")

    @pytest.mark.parametrize("fmt,label", EXPORT_FORMATS)
    def test_export_link_present(self, published_dataset, fmt, label):
        """Each export format should have a link with the correct text and href."""
        page, container_uuid = published_dataset
        page.goto(f"/datasets/{container_uuid}")
        page.wait_for_load_state("domcontentloaded")
        page.locator("#export").wait_for(state="visible", timeout=15000)

        link = page.locator(f"#export a[href*='/export/{fmt}/datasets/']")
        expect(link).to_be_visible()
        expect(link).to_have_text(label)


# ---------------------------------------------------------------------------
# Export download tests
# ---------------------------------------------------------------------------


@pytest.mark.citation
class TestExportDownload:
    """Test downloading each export format and verifying non-empty responses."""

    @pytest.mark.parametrize("fmt,label", EXPORT_FORMATS)
    def test_export_download_non_empty(self, published_dataset, fmt, label, screenshot):
        """Downloading each export format should return a non-empty response."""
        page, container_uuid = published_dataset
        page.goto(f"/datasets/{container_uuid}")
        page.wait_for_load_state("domcontentloaded")
        page.locator("#export").wait_for(state="visible", timeout=15000)

        # Extract the actual export href from the page
        link = page.locator(f"#export a[href*='/export/{fmt}/datasets/']")
        href = link.get_attribute("href")
        assert href, f"Export link for {label} should have an href"

        # Use the API context to fetch the export with appropriate Accept header
        xml_formats = {"refworks", "datacite", "nlm", "dc"}
        accept = "application/xml" if fmt in xml_formats else "text/plain"

        response = page.request.get(href, headers={"Accept": accept})
        assert response.ok, f"{label} export failed: {response.status}"

        body = response.body()
        assert len(body) > 0, f"{label} export should return non-empty content"

        screenshot(page, f"export-{fmt}-downloaded")
