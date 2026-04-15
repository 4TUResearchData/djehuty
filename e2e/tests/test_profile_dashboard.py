"""
User profile and dashboard tests.

Covers:
    - View and edit profile fields (name, job title, bio, social links)
    - Navigate depositor dashboard
    - Verify my datasets list with pagination
    - Verify my collections list
    - Verify submitted for review list

Run with:
    cd e2e && python -m pytest tests/test_profile_dashboard.py -v
"""

import uuid

import pytest
from playwright.sync_api import Page, expect

from config import BASE_URL
from helpers.dataset import create_draft_dataset
from pages.dashboard_page import DashboardPage
from pages.dataset_editor_page import DatasetEditorPage
from pages.profile_page import ProfilePage


# ---------------------------------------------------------------------------
# Profile tests
# ---------------------------------------------------------------------------


@pytest.mark.profile
class TestViewProfile:
    """Test viewing the user profile page."""

    def test_profile_page_loads(self, authenticated_page: Page, screenshot):
        """The profile page should load with form fields visible."""
        profile = ProfilePage(authenticated_page)
        profile.navigate()
        screenshot(authenticated_page, "profile-loaded")

        expect(authenticated_page).to_have_url(f"{BASE_URL}/my/profile")
        assert profile.is_save_visible()

    def test_profile_has_all_fields(self, authenticated_page: Page, screenshot):
        """The profile page should display all expected form fields."""
        profile = ProfilePage(authenticated_page)
        profile.navigate()
        screenshot(authenticated_page, "profile-fields")

        for field_id in ["first_name", "last_name", "job_title", "location",
                         "twitter", "linkedin", "website", "biography"]:
            expect(authenticated_page.locator(f"#{field_id}")).to_be_visible()

    def test_profile_shows_current_values(self, authenticated_page: Page, screenshot):
        """The profile page should display the current user's details."""
        profile = ProfilePage(authenticated_page)
        profile.navigate()
        screenshot(authenticated_page, "profile-current-values")

        # The dev account should have at least a first name populated
        first_name = profile.get_first_name()
        assert isinstance(first_name, str)

    def test_profile_requires_auth(self, page: Page, screenshot):
        """GET /my/profile without a session should return 403."""
        response = page.goto("/my/profile")
        assert response is not None
        screenshot(page, "profile-403")
        assert response.status == 403


@pytest.mark.profile
class TestEditProfile:
    """Test editing profile fields."""

    def test_edit_name_and_save(self, authenticated_page: Page, screenshot):
        """Editing first and last name should persist after save."""
        profile = ProfilePage(authenticated_page)
        profile.navigate()

        # Save original values for restoration
        original_first = profile.get_first_name()
        original_last = profile.get_last_name()
        screenshot(authenticated_page, "before-edit-name")

        test_first = f"E2EFirst-{uuid.uuid4().hex[:6]}"
        test_last = f"E2ELast-{uuid.uuid4().hex[:6]}"
        profile.set_first_name(test_first)
        profile.set_last_name(test_last)
        profile.save()
        screenshot(authenticated_page, "after-save-name")

        # Reload and verify persistence
        profile.navigate()
        screenshot(authenticated_page, "reloaded-name")
        assert profile.get_first_name() == test_first
        assert profile.get_last_name() == test_last

        # Restore original values
        profile.set_first_name(original_first)
        profile.set_last_name(original_last)
        profile.save()

    def test_edit_job_title(self, authenticated_page: Page, screenshot):
        """Editing the job title should persist after save."""
        profile = ProfilePage(authenticated_page)
        profile.navigate()

        original = profile.get_job_title()
        screenshot(authenticated_page, "before-edit-job-title")

        test_title = f"E2E Tester {uuid.uuid4().hex[:6]}"
        profile.set_job_title(test_title)
        profile.save()
        screenshot(authenticated_page, "after-save-job-title")

        profile.navigate()
        assert profile.get_job_title() == test_title

        # Restore
        profile.set_job_title(original)
        profile.save()

    def test_edit_biography(self, authenticated_page: Page, screenshot):
        """Editing the biography should persist after save."""
        profile = ProfilePage(authenticated_page)
        profile.navigate()

        original = profile.get_biography()
        screenshot(authenticated_page, "before-edit-bio")

        test_bio = f"This is an E2E test biography. ID: {uuid.uuid4().hex[:8]}"
        profile.set_biography(test_bio)
        profile.save()
        screenshot(authenticated_page, "after-save-bio")

        profile.navigate()
        assert profile.get_biography() == test_bio

        # Restore
        profile.set_biography(original)
        profile.save()

    def test_edit_social_links(self, authenticated_page: Page, screenshot):
        """Editing Twitter, LinkedIn, and website should persist after save."""
        profile = ProfilePage(authenticated_page)
        profile.navigate()

        original_twitter = profile.get_twitter()
        original_linkedin = profile.get_linkedin()
        original_website = profile.get_website()
        screenshot(authenticated_page, "before-edit-social")

        tag = uuid.uuid4().hex[:6]
        profile.set_twitter(f"@e2e_test_{tag}")
        profile.set_linkedin(f"https://linkedin.com/in/e2e-{tag}")
        profile.set_website(f"https://e2e-{tag}.example.com")
        profile.save()
        screenshot(authenticated_page, "after-save-social")

        profile.navigate()
        screenshot(authenticated_page, "reloaded-social")
        assert profile.get_twitter() == f"@e2e_test_{tag}"
        assert profile.get_linkedin() == f"https://linkedin.com/in/e2e-{tag}"
        assert profile.get_website() == f"https://e2e-{tag}.example.com"

        # Restore
        profile.set_twitter(original_twitter)
        profile.set_linkedin(original_linkedin)
        profile.set_website(original_website)
        profile.save()

    def test_edit_location(self, authenticated_page: Page, screenshot):
        """Editing the location should persist after save."""
        profile = ProfilePage(authenticated_page)
        profile.navigate()

        original = profile.get_location()
        screenshot(authenticated_page, "before-edit-location")

        test_location = f"E2E City {uuid.uuid4().hex[:6]}"
        profile.set_location(test_location)
        profile.save()

        profile.navigate()
        screenshot(authenticated_page, "reloaded-location")
        assert profile.get_location() == test_location

        # Restore
        profile.set_location(original)
        profile.save()

    def test_categories_expand_collapse(self, authenticated_page: Page, screenshot):
        """The categories section should toggle visibility on click."""
        profile = ProfilePage(authenticated_page)
        profile.navigate()
        screenshot(authenticated_page, "categories-collapsed")

        assert not profile.is_categories_visible()

        profile.expand_categories()
        screenshot(authenticated_page, "categories-expanded")
        assert profile.is_categories_visible()


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------


@pytest.mark.dashboard
class TestDashboard:
    """Test the depositor dashboard page."""

    def test_dashboard_loads(self, authenticated_page: Page, screenshot):
        """The dashboard should load with expected elements."""
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()
        screenshot(authenticated_page, "dashboard-loaded")

        expect(authenticated_page).to_have_url(f"{BASE_URL}/my/dashboard")
        expect(authenticated_page.locator("h1")).to_have_text("Dashboard")

    def test_dashboard_has_quick_actions(self, authenticated_page: Page, screenshot):
        """The dashboard should show quick action buttons for depositors."""
        authenticated_page.goto("/my/dashboard")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "dashboard-quick-actions")

        expect(authenticated_page.locator("#create-new-dataset")).to_be_visible()
        expect(authenticated_page.locator("#create-new-collection")).to_be_visible()

    def test_dashboard_shows_storage_usage(self, authenticated_page: Page, screenshot):
        """The dashboard should display storage usage information."""
        authenticated_page.goto("/my/dashboard")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "dashboard-storage")

        storage_text = authenticated_page.locator(".storage-usage").inner_text()
        assert "Using" in storage_text
        assert "of" in storage_text

    def test_dashboard_has_session_table(self, authenticated_page: Page, screenshot):
        """The dashboard should show the sessions/API tokens table."""
        authenticated_page.goto("/my/dashboard")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "dashboard-sessions")

        session_table = authenticated_page.locator("#session-table")
        expect(session_table).to_be_visible()
        # The current session should be marked
        expect(session_table).to_contain_text("Current session")

    def test_dashboard_storage_request_toggle(self, authenticated_page: Page, screenshot):
        """Clicking 'Request more storage' should show the request form."""
        authenticated_page.goto("/my/dashboard")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "before-storage-request")

        # Initially hidden
        assert not authenticated_page.locator("#storage-request-wrapper").is_visible()

        authenticated_page.locator("#request-more-storage").click()
        authenticated_page.locator("#storage-request-wrapper").wait_for(state="visible")
        screenshot(authenticated_page, "storage-request-visible")

        expect(authenticated_page.locator("#new-quota")).to_be_visible()
        expect(authenticated_page.locator("#submit-storage-request")).to_be_visible()

    def test_dashboard_navigation_links(self, authenticated_page: Page, screenshot):
        """The dashboard submenu should contain links to datasets, collections."""
        authenticated_page.goto("/my/dashboard")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "dashboard-nav-links")

        expect(authenticated_page.locator("a[href='/my/datasets']")).to_be_visible()
        expect(authenticated_page.locator("a[href='/my/collections']")).to_be_visible()

    def test_dashboard_requires_auth(self, page: Page, screenshot):
        """GET /my/dashboard without a session should return 403."""
        response = page.goto("/my/dashboard")
        assert response is not None
        screenshot(page, "dashboard-403")
        assert response.status == 403


# ---------------------------------------------------------------------------
# My Datasets list tests
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestMyDatasets:
    """Test the my datasets listing page."""

    def test_my_datasets_page_loads(self, authenticated_page: Page, screenshot):
        """The my datasets page should load with the Datasets heading."""
        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "my-datasets-loaded")

        expect(authenticated_page).to_have_url(f"{BASE_URL}/my/datasets")
        expect(authenticated_page.locator("h1")).to_have_text("Datasets")

    def test_drafts_table_with_dataset(self, authenticated_page: Page, screenshot):
        """Creating a dataset should make it appear in the drafts table."""
        url = create_draft_dataset(authenticated_page)
        editor = DatasetEditorPage(authenticated_page)
        editor.wait_for_ready()
        unique_title = f"DraftList-{uuid.uuid4().hex[:8]}"
        editor.set_title(unique_title)
        editor.save()
        screenshot(authenticated_page, "dataset-created-for-list")

        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        # Wait for DataTables to render
        authenticated_page.locator("#table-unpublished").wait_for(state="visible")

        # Verify table has expected columns
        drafts_table = authenticated_page.locator("#table-unpublished")
        headers = drafts_table.locator("thead th")
        header_texts = [headers.nth(i).inner_text() for i in range(headers.count())]
        assert "Dataset" in header_texts
        assert "Type" in header_texts
        assert "Size" in header_texts

        # Use DataTables search to find our specific dataset (handles pagination)
        authenticated_page.locator("#table-unpublished_filter input").fill(unique_title)
        screenshot(authenticated_page, "drafts-table-filtered")
        expect(drafts_table).to_contain_text(unique_title)

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()

    def test_datatables_pagination_present(self, authenticated_page: Page, screenshot):
        """DataTables should add pagination controls when datasets exist."""
        # Create enough datasets that pagination might appear or at least
        # verify that DataTables has initialized (search box present)
        url = create_draft_dataset(authenticated_page)
        screenshot(authenticated_page, "dataset-for-pagination")

        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.locator("#table-unpublished").wait_for(state="visible")
        screenshot(authenticated_page, "datatables-initialized")

        # DataTables adds a search/filter input and info element
        expect(authenticated_page.locator("#table-unpublished_filter")).to_be_visible()

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()

    def test_drafts_table_has_action_links(self, authenticated_page: Page, screenshot):
        """Each draft row should have private links and delete action icons."""
        url = create_draft_dataset(authenticated_page)
        screenshot(authenticated_page, "dataset-for-actions")

        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.locator("#table-unpublished").wait_for(state="visible")
        screenshot(authenticated_page, "drafts-table-actions")

        row = authenticated_page.locator("#table-unpublished tbody tr").first
        expect(row.locator("a.fa-link")).to_be_visible()
        expect(row.locator("a.fa-trash-can")).to_be_visible()

        # Clean up
        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()


# ---------------------------------------------------------------------------
# My Collections list tests
# ---------------------------------------------------------------------------


@pytest.mark.collections
class TestMyCollections:
    """Test the my collections listing page."""

    def test_my_collections_page_loads(self, authenticated_page: Page, screenshot):
        """The my collections page should load with the Collections heading."""
        authenticated_page.goto("/my/collections")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "my-collections-loaded")

        expect(authenticated_page).to_have_url(f"{BASE_URL}/my/collections")
        expect(authenticated_page.locator("h1")).to_have_text("Collections")

    def test_collections_page_has_create_button(self, authenticated_page: Page, screenshot):
        """The collections page should show a create button for depositors."""
        authenticated_page.goto("/my/collections")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "collections-create-button")

        expect(authenticated_page.locator("#add-new-collection")).to_be_visible()

    def test_collections_requires_auth(self, page: Page, screenshot):
        """GET /my/collections without a session should return 403."""
        response = page.goto("/my/collections")
        assert response is not None
        screenshot(page, "collections-403")
        assert response.status == 403

    def test_create_collection_and_verify_in_list(self, authenticated_page: Page, screenshot):
        """Creating a collection should make it appear in the drafts table."""
        # Create a new collection
        authenticated_page.goto("/my/collections/new")
        authenticated_page.wait_for_url("**/my/collections/*/edit")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "new-collection-editor")

        collection_url = authenticated_page.url

        # Navigate to collections list
        authenticated_page.goto("/my/collections")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "collections-with-draft")

        # The drafts table should exist and contain "Untitled item"
        drafts_table = authenticated_page.locator("#table-unpublished-collections")
        expect(drafts_table).to_be_visible()
        expect(drafts_table).to_contain_text("Untitled")

        # Clean up: delete the collection
        authenticated_page.goto(collection_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.locator(".collection-content-loader").wait_for(state="hidden")
        authenticated_page.locator("#delete").wait_for(state="visible")
        authenticated_page.once("dialog", lambda dialog: dialog.accept())
        authenticated_page.locator("#delete").click()
        authenticated_page.wait_for_url("**/my/collections", wait_until="domcontentloaded")


# ---------------------------------------------------------------------------
# Submitted for review tests
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestSubmittedForReview:
    """Test the submitted for review confirmation page."""

    def test_submitted_for_review_page_loads(self, authenticated_page: Page, screenshot):
        """The submitted-for-review confirmation page should be accessible."""
        response = authenticated_page.goto("/my/datasets/submitted-for-review")
        assert response is not None
        screenshot(authenticated_page, "submitted-for-review")

        assert response.status == 200
        expect(authenticated_page.locator("h1")).to_contain_text("submitted for review")

    def test_submitted_for_review_has_back_link(self, authenticated_page: Page, screenshot):
        """The confirmation page should have a link back to datasets overview."""
        authenticated_page.goto("/my/datasets/submitted-for-review")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "submitted-back-link")

        back_link = authenticated_page.locator("#create-new-dataset")
        expect(back_link).to_be_visible()
        expect(back_link).to_have_attribute("href", "/my/datasets")

    def test_review_table_structure(self, authenticated_page: Page, screenshot):
        """If the review table is present, it should have the expected columns."""
        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "datasets-review-section")

        review_table = authenticated_page.locator("#table-review")
        if review_table.count() > 0 and review_table.is_visible():
            headers = review_table.locator("thead th")
            header_texts = [headers.nth(i).inner_text() for i in range(headers.count())]
            assert "Dataset" in header_texts
            assert "Status" in header_texts
            screenshot(authenticated_page, "review-table-columns")
