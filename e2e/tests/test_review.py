"""
Publication & review workflow tests.

Covers:
    - Submit dataset for review (via API, verify confirmation)
    - Navigate to review overview page as reviewer
    - Assign dataset to self as reviewer
    - Approve/publish dataset through review interface
    - Decline dataset and verify return to draft
    - Verify DOI appears after publication

Run with:
    cd e2e && python -m pytest tests/test_review.py -v
"""

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from helpers.dataset import (
    create_draft_dataset,
    get_container_uuid_from_url,
    get_dataset_uuid_from_editor,
)
from helpers.publish import fill_required_fields_and_publish
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_FILE_CONTENT = b"Review workflow test file.\n"
TEST_FILE_NAME = "review-test-file.txt"


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    """Create a temporary test file and return its path."""
    file_path = tmp_path / TEST_FILE_NAME
    file_path.write_bytes(TEST_FILE_CONTENT)
    return str(file_path)


def submit_for_review_via_api(page: Page, container_uuid: str, title: str = "Review Test"):
    """Submit a dataset for review using the API.

    Fills required fields (tag, author, category) via API, sets title/description
    via the editor UI, then submits via the PUT endpoint. Returns the dataset_uuid.
    """
    page.goto(f"/my/datasets/{container_uuid}/edit")
    page.wait_for_load_state("domcontentloaded")
    page.locator(".article-content").wait_for(state="visible")

    # Extract IDs from the editor form
    group_id = page.evaluate(
        "() => { let g = document.querySelector(\"input[name='groups']\"); "
        "return g ? g.value : null; }"
    )
    category_uuid = page.evaluate(
        "() => { let c = document.querySelector(\"input[name='categories']\"); "
        "return c ? c.value : null; }"
    )
    license_id = page.evaluate(
        "() => { let opt = document.querySelector('#license_open option:not([disabled])'); "
        "return opt ? opt.value : '2'; }"
    )
    dataset_uuid = get_dataset_uuid_from_editor(page)

    # Add required metadata via API
    page.request.post(
        f"/v3/datasets/{container_uuid}/tags",
        data={"tags": ["e2e-review-test"]},
    )
    page.request.post(
        f"/v2/account/articles/{container_uuid}/authors",
        data={"authors": [{"first_name": "Test", "last_name": "Author"}]},
    )
    if category_uuid:
        page.request.post(
            f"/v2/account/articles/{container_uuid}/categories",
            data={"categories": [category_uuid]},
        )

    # Set title/description in the editor and save
    editor = DatasetEditorPage(page)
    editor.set_title(title)
    editor.set_description(f"<p>Description for {title}.</p>")
    editor.save()

    # Submit for review via API
    form_data = {
        "title": title,
        "description": f"<p>Description for {title}.</p>",
        "defined_type": "dataset",
        "is_embargoed": False,
        "is_metadata_record": False,
        "agreed_to_deposit_agreement": True,
        "agreed_to_publish": True,
        "categories": [category_uuid] if category_uuid else [],
        "group_id": int(group_id) if group_id else None,
        "license_id": int(license_id) if license_id else 2,
        "publisher": "4TU.ResearchData",
        "language": "en",
    }
    response = page.request.put(
        f"/v3/datasets/{container_uuid}/submit-for-review",
        data=form_data,
    )
    assert response.ok, f"Submit failed: {response.status} {response.text()}"

    return dataset_uuid


# ---------------------------------------------------------------------------
# Submit for review tests
# ---------------------------------------------------------------------------


@pytest.mark.review
class TestSubmitForReview:
    """Test the submission workflow."""

    def test_submit_confirmation_page(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """After submission, the confirmation page should be shown."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        submit_for_review_via_api(authenticated_page, container_uuid,
                                  title="Submit Confirmation Test")

        # Visit the confirmation page
        authenticated_page.goto("/my/datasets/submitted-for-review")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "submitted-for-review")

        expect(authenticated_page.locator("h1")).to_contain_text(
            "submitted for review"
        )

    def test_submit_button_hidden_after_submission(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """After submission, the submit button should not be visible on the editor."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        submit_for_review_via_api(authenticated_page, container_uuid,
                                  title="Submit Hidden Test")

        # Go back to the editor
        authenticated_page.goto(f"/my/datasets/{container_uuid}/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "editor-after-submit")

        # Submit button should be hidden (dataset is under review)
        assert not editor.is_submit_visible()


# ---------------------------------------------------------------------------
# Review overview tests
# ---------------------------------------------------------------------------


@pytest.mark.review
class TestReviewOverview:
    """Test the reviewer overview page."""

    def test_review_overview_shows_submitted_dataset(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """A submitted dataset should appear on the review overview page."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        submit_for_review_via_api(authenticated_page, container_uuid,
                                  title="Overview Visible Test")

        # Navigate to review overview
        authenticated_page.goto("/review/overview")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.locator("#overview-table").wait_for(state="visible")
        screenshot(authenticated_page, "review-overview")

        expect(authenticated_page.locator("#overview-table tbody")).to_contain_text(
            "Overview Visible Test"
        )

    def test_review_overview_status_filters(
        self, authenticated_page: Page, screenshot
    ):
        """The status filter dropdown should filter the review table."""
        authenticated_page.goto("/review/overview")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.locator("#overview-table").wait_for(state="visible")
        screenshot(authenticated_page, "overview-before-filter")

        # Select "unassigned" status filter
        authenticated_page.locator(".status-filter").select_option("unassigned")
        authenticated_page.wait_for_timeout(500)
        screenshot(authenticated_page, "overview-filtered-unassigned")

        # All visible rows should have "unassigned" in the status column
        visible_rows = authenticated_page.locator(
            "#overview-table tbody tr:visible"
        )
        for i in range(visible_rows.count()):
            status_cell = visible_rows.nth(i).locator("td:nth-child(6)")
            expect(status_cell).to_contain_text("unassigned")


# ---------------------------------------------------------------------------
# Assign reviewer tests
# ---------------------------------------------------------------------------


@pytest.mark.review
class TestAssignReviewer:
    """Test assigning a reviewer to a submitted dataset."""

    def test_assign_reviewer_via_dropdown(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """Selecting a reviewer from the dropdown should assign them."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        submit_for_review_via_api(authenticated_page, container_uuid,
                                  title="Assign Reviewer Test")

        # Go to review overview
        authenticated_page.goto("/review/overview")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.locator("#overview-table").wait_for(state="visible")
        screenshot(authenticated_page, "overview-before-assign")

        # Find the first row matching our dataset title
        row = authenticated_page.locator(
            "#overview-table tbody tr",
            has_text="Assign Reviewer Test"
        ).first
        reviewer_select = row.locator(".reviewer-selector")

        # Select the first available reviewer
        options = reviewer_select.locator("option:not([value=''])")
        first_option_value = options.first.get_attribute("value")
        reviewer_select.select_option(first_option_value)

        # Wait for the AJAX to update the status icon (hourglass → glasses)
        status_cell = row.locator("td:nth-child(6)")
        expect(status_cell).to_contain_text("assigned", timeout=5000)
        screenshot(authenticated_page, "overview-after-assign")


# ---------------------------------------------------------------------------
# Publish (approve) tests
# ---------------------------------------------------------------------------


@pytest.mark.review
class TestPublishDataset:
    """Test approving and publishing a dataset through the review interface."""

    def test_reviewer_sees_publish_and_decline_buttons(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """A reviewer entering review mode should see Publish and Decline buttons."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        dataset_uuid = submit_for_review_via_api(
            authenticated_page, container_uuid, title="Buttons Visible Test"
        )

        # Enter review mode
        authenticated_page.goto(f"/review/goto-dataset/{dataset_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.locator(".article-content").wait_for(state="visible")
        screenshot(authenticated_page, "reviewer-buttons-visible")

        expect(authenticated_page.locator("#publish")).to_be_visible()
        expect(authenticated_page.locator("#decline")).to_be_visible()
        # Submit button should NOT be visible during review
        assert not authenticated_page.locator("#submit").is_visible()

        # Log out of review mode to clean up
        authenticated_page.goto("/logout")
        authenticated_page.wait_for_load_state("domcontentloaded")

    def test_publish_via_review_interface(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """A reviewer should be able to publish a dataset via the Publish button."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        dataset_uuid = submit_for_review_via_api(
            authenticated_page, container_uuid, title="Publish Via UI Test"
        )

        # Enter review mode
        authenticated_page.goto(f"/review/goto-dataset/{dataset_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.locator(".article-content").wait_for(state="visible")
        screenshot(authenticated_page, "before-publish")

        # Click Publish — JS saves first, then POSTs to /publish, then redirects to /logout
        authenticated_page.locator("#publish").click()
        # After publish + logout, reviewer returns to the review section
        authenticated_page.wait_for_url("**/review/**", timeout=60000)
        screenshot(authenticated_page, "after-publish")

    def test_published_dataset_accessible_on_public_page(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """A published dataset should be accessible on its public page."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="Public Access Test",
        )

        # After publish, the session may be in review state. Navigate directly.
        response = authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert response is not None
        screenshot(authenticated_page, "published-dataset-public")
        assert response.status == 200

        # Verify the dataset page has content (title shown in the page)
        expect(authenticated_page.locator("#metadata")).to_be_visible()

    def test_doi_section_on_published_dataset(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """A published dataset page should show the DOI section."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        fill_required_fields_and_publish(
            authenticated_page,
            container_uuid,
            title="DOI Section Test",
            description="<p>Testing DOI section display.</p>",
        )

        # Visit the public dataset page
        authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "public-dataset-with-doi")

        # The DOI section should be present on the published page
        doi_element = authenticated_page.locator("#doi")
        expect(doi_element).to_be_visible()
        # The DOI label should be visible
        expect(authenticated_page.locator("#doi .doi-label")).to_be_visible()
        screenshot(authenticated_page, "doi-section-displayed")


# ---------------------------------------------------------------------------
# Decline tests
# ---------------------------------------------------------------------------


@pytest.mark.review
class TestDeclineDataset:
    """Test declining a dataset through the review interface."""

    def test_decline_returns_to_draft(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """Declining a dataset should return it to draft (not under review)."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        dataset_uuid = submit_for_review_via_api(
            authenticated_page, container_uuid, title="Decline Test Dataset"
        )
        screenshot(authenticated_page, "submitted-before-decline")

        # Enter review mode
        authenticated_page.goto(f"/review/goto-dataset/{dataset_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.locator(".article-content").wait_for(state="visible")
        screenshot(authenticated_page, "reviewer-before-decline")

        # Click Decline
        authenticated_page.locator("#decline").click()
        authenticated_page.wait_for_url("**/review/**", timeout=60000)
        screenshot(authenticated_page, "after-decline")

        # Login fresh and revisit the editor
        authenticated_page.goto("/login")
        authenticated_page.wait_for_url("**/my/dashboard**")
        authenticated_page.goto(f"/my/datasets/{container_uuid}/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        screenshot(authenticated_page, "dataset-back-to-draft")

        # The submit button should be visible again
        assert editor.is_submit_visible()

        # Clean up
        editor.delete()

    def test_declined_shows_in_review_overview(
        self, authenticated_page: Page, test_file: str, screenshot
    ):
        """A declined dataset should show 'declined' status in the overview."""
        url = create_draft_dataset(authenticated_page)
        container_uuid = get_container_uuid_from_url(url)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        editor.upload_file(test_file)
        editor.save()

        dataset_uuid = submit_for_review_via_api(
            authenticated_page, container_uuid, title="Decline Status Test"
        )

        # Enter review mode and decline
        authenticated_page.goto(f"/review/goto-dataset/{dataset_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.wait_for_url("**/my/datasets/*/edit")
        authenticated_page.locator(".article-content").wait_for(state="visible")
        authenticated_page.locator("#decline").click()
        authenticated_page.wait_for_url("**/review/**", timeout=60000)

        # Login and check overview
        authenticated_page.goto("/login")
        authenticated_page.wait_for_url("**/my/dashboard**")
        authenticated_page.goto("/review/overview")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.locator("#overview-table").wait_for(state="visible")

        # Filter to declined
        authenticated_page.locator(".status-filter").select_option("declined")
        authenticated_page.wait_for_timeout(500)
        screenshot(authenticated_page, "declined-in-overview")

        expect(authenticated_page.locator("#overview-table tbody")).to_contain_text(
            "Decline Status Test"
        )

        # Clean up
        authenticated_page.goto(f"/my/datasets/{container_uuid}/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()
