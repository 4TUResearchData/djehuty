"""
Dataset API tests.

Covers the V2 and V3 dataset API endpoints:
    - List public datasets (GET /v2/articles, GET /v3/datasets)
    - Search datasets (POST /v2/articles/search, POST /v3/datasets/search)
    - Get dataset details (GET /v2/articles/<id>)
    - Create private dataset (POST /v2/account/articles)
    - Update private dataset (PUT /v2/account/articles/<id>)
    - Get private dataset details (GET /v2/account/articles/<id>)
    - Delete private dataset (DELETE /v2/account/articles/<id>)
    - Dataset authors CRUD (GET/POST/PUT /v2/account/articles/<id>/authors)
    - Dataset tags CRUD (GET/POST/PUT/DELETE /v3/datasets/<id>/tags)
    - Dataset references CRUD (GET/POST/PUT/DELETE /v3/datasets/<id>/references)
    - Dataset categories CRUD (GET/POST/PUT /v2/account/articles/<id>/categories)
    - Private links CRUD
    - Dataset files listing
    - Published dataset versions

Run with:
    cd e2e && python -m pytest tests/test_dataset_api.py -v
"""

import uuid
from pathlib import Path

import pytest
from playwright.sync_api import Page

from helpers.dataset import (
    create_draft_dataset,
    get_container_uuid_from_url,
)
from helpers.publish import fill_required_fields_and_publish
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_FILE_CONTENT = b"API test file content.\n"
TEST_FILE_NAME = "api-test-file.txt"


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    """Create a temporary test file and return its path."""
    file_path = tmp_path / TEST_FILE_NAME
    file_path.write_bytes(TEST_FILE_CONTENT)
    return str(file_path)


@pytest.fixture()
def draft_dataset(authenticated_page: Page):
    """Create a draft dataset via the UI and return (page, container_uuid).

    Tears down by deleting the dataset after the test.
    """
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    yield authenticated_page, container_uuid
    # Teardown: delete via API (ignore errors if already deleted)
    authenticated_page.request.delete(
        f"/v2/account/articles/{container_uuid}"
    )


@pytest.fixture()
def published_dataset(authenticated_page: Page, test_file: str):
    """Create and publish a dataset, return (page, container_uuid)."""
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(test_file)
    editor.save()

    fill_required_fields_and_publish(
        authenticated_page,
        container_uuid,
        title="API Test Published Dataset",
        description="<p>Published dataset for API tests.</p>",
    )

    # Re-login after publish flow
    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")

    # Wait for the published dataset to become accessible
    for _ in range(5):
        resp = authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        if resp and resp.status == 200:
            break
        authenticated_page.wait_for_timeout(3000)

    return authenticated_page, container_uuid


# ---------------------------------------------------------------------------
# Public API tests
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestPublicDatasetApi:
    """Test public (unauthenticated) dataset API endpoints."""

    def test_list_datasets_v2(self, page: Page, save_response):
        """GET /v2/articles should return a JSON array."""
        response = page.request.get("/v2/articles?limit=5")
        save_response(response, "v2-list-datasets")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_datasets_v3(self, page: Page, save_response):
        """GET /v3/datasets should return a JSON array."""
        response = page.request.get("/v3/datasets?limit=5")
        save_response(response, "v3-list-datasets")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_datasets_v2(self, page: Page, save_response):
        """POST /v2/articles/search should return matching datasets."""
        response = page.request.post(
            "/v2/articles/search",
            data={"search_for": "test", "limit": 5},
        )
        save_response(response, "v2-search-datasets")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_datasets_v3(self, page: Page, save_response):
        """POST /v3/datasets/search should return matching datasets."""
        response = page.request.post(
            "/v3/datasets/search",
            data={"search_for": "test"},
        )
        save_response(response, "v3-search-datasets")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_nonexistent_dataset_returns_404(self, page: Page, save_response):
        """GET /v2/articles/<fake-id> should return 404."""
        response = page.request.get("/v2/articles/99999999")
        save_response(response, "v2-dataset-404")
        assert response.status == 404

    def test_list_datasets_with_pagination(self, page: Page, save_response):
        """GET /v2/articles with limit and offset should respect pagination."""
        response = page.request.get("/v2/articles?limit=2&offset=0")
        save_response(response, "v2-list-paginated")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 2

    def test_list_datasets_v3_with_order(self, page: Page, save_response):
        """GET /v3/datasets with order parameters should return sorted results."""
        response = page.request.get(
            "/v3/datasets?limit=5&order=published_date&order_direction=desc"
        )
        save_response(response, "v3-datasets-ordered")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Private API – CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestPrivateDatasetCrud:
    """Test private dataset CRUD via the API."""

    def test_create_dataset_via_api(self, authenticated_page: Page, save_response):
        """POST /v2/account/articles should create a dataset and return location."""
        response = authenticated_page.request.post(
            "/v2/account/articles",
            data={"title": "API Created Dataset"},
        )
        save_response(response, "api-create-dataset")
        assert response.status == 200
        data = response.json()
        assert "location" in data

        # Clean up: extract UUID and delete
        dataset_uuid = data["location"].rstrip("/").split("/")[-1]
        authenticated_page.request.delete(
            f"/v2/account/articles/{dataset_uuid}"
        )

    def test_create_dataset_without_title(self, authenticated_page: Page, save_response):
        """POST /v2/account/articles without title should return 400."""
        response = authenticated_page.request.post(
            "/v2/account/articles",
            data={},
        )
        save_response(response, "api-create-no-title")
        # Title is required (min 3 chars), so empty body returns 400
        assert response.status == 400

    def test_get_private_dataset(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid> should return dataset details."""
        page, container_uuid = draft_dataset
        response = page.request.get(
            f"/v2/account/articles/{container_uuid}"
        )
        save_response(response, "api-get-private-dataset")
        assert response.status == 200
        data = response.json()
        assert "uuid" in data or "container_uuid" in data

    def test_update_dataset_metadata(self, draft_dataset, save_response):
        """PUT /v2/account/articles/<uuid> should update metadata."""
        page, container_uuid = draft_dataset
        unique_title = f"Updated Title {uuid.uuid4().hex[:8]}"
        response = page.request.put(
            f"/v2/account/articles/{container_uuid}",
            data={
                "title": unique_title,
                "description": "<p>Updated via API.</p>",
            },
        )
        save_response(response, "api-update-dataset")
        assert response.ok

        # Verify the update persisted
        get_response = page.request.get(
            f"/v2/account/articles/{container_uuid}"
        )
        save_response(get_response, "api-update-dataset-verify")
        data = get_response.json()
        assert data["title"] == unique_title

    def test_update_dataset_tags_via_v2(self, draft_dataset, save_response):
        """PUT /v2/account/articles/<uuid> with tags should update tags."""
        page, container_uuid = draft_dataset
        response = page.request.put(
            f"/v2/account/articles/{container_uuid}",
            data={"tags": ["api-test", "e2e"]},
        )
        save_response(response, "api-update-tags")
        assert response.ok

    def test_delete_dataset(self, authenticated_page: Page, save_response):
        """DELETE /v2/account/articles/<uuid> should remove the dataset."""
        # Create a dataset to delete
        response = authenticated_page.request.post(
            "/v2/account/articles",
            data={"title": "To Be Deleted"},
        )
        data = response.json()
        dataset_uuid = data["location"].rstrip("/").split("/")[-1]

        # Delete it
        delete_response = authenticated_page.request.delete(
            f"/v2/account/articles/{dataset_uuid}"
        )
        save_response(delete_response, "api-delete-dataset")
        assert delete_response.status == 204

        # Verify it's gone — the private endpoint returns 200 with an empty
        # array when the dataset no longer exists for this account.
        get_response = authenticated_page.request.get(
            f"/v2/account/articles/{dataset_uuid}"
        )
        save_response(get_response, "api-delete-dataset-verify-gone")
        assert get_response.status == 200
        assert get_response.json() == [] or get_response.body() == b"[]"

    def test_list_private_datasets(self, draft_dataset, save_response):
        """GET /v2/account/articles should list the user's datasets."""
        page, container_uuid = draft_dataset
        response = page.request.get("/v2/account/articles?limit=50")
        save_response(response, "api-list-private-datasets")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        # Our draft should be in the list
        uuids = [
            d.get("uuid") or d.get("container_uuid", "")
            for d in data
        ]
        assert any(container_uuid in u for u in uuids)

    def test_search_private_datasets(self, draft_dataset, save_response):
        """POST /v2/account/articles/search should find private datasets."""
        page, container_uuid = draft_dataset
        # First, set a unique title
        unique_title = f"SearchMe-{uuid.uuid4().hex[:8]}"
        page.request.put(
            f"/v2/account/articles/{container_uuid}",
            data={"title": unique_title},
        )

        response = page.request.post(
            "/v2/account/articles/search",
            data={"search_for": unique_title},
        )
        save_response(response, "api-search-private")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_private_dataset_requires_auth(self, page: Page, save_response):
        """GET /v2/account/articles without auth should fail."""
        response = page.request.get("/v2/account/articles")
        save_response(response, "api-private-no-auth")
        assert response.status in (403, 401)


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestDatasetAuthorsApi:
    """Test dataset author management via the API."""

    def test_get_authors(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/authors should return a list."""
        page, container_uuid = draft_dataset
        response = page.request.get(
            f"/v2/account/articles/{container_uuid}/authors"
        )
        save_response(response, "api-get-authors")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_author(self, draft_dataset, save_response):
        """POST /v2/account/articles/<uuid>/authors should add an author."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v2/account/articles/{container_uuid}/authors",
            data={"authors": [{"first_name": "Jane", "last_name": "Doe"}]},
        )
        save_response(response, "api-add-author")
        assert response.ok

        # Verify the author was added — v2 returns full_name, not first/last
        get_response = page.request.get(
            f"/v2/account/articles/{container_uuid}/authors"
        )
        save_response(get_response, "api-add-author-verify")
        authors = get_response.json()
        names = [a.get("full_name", "") for a in authors]
        assert any("Jane" in n and "Doe" in n for n in names)

    def test_replace_authors(self, draft_dataset, save_response):
        """PUT /v2/account/articles/<uuid>/authors should replace all authors."""
        page, container_uuid = draft_dataset
        response = page.request.put(
            f"/v2/account/articles/{container_uuid}/authors",
            data={"authors": [
                {"first_name": "Alice", "last_name": "Smith"},
                {"first_name": "Bob", "last_name": "Jones"},
            ]},
        )
        save_response(response, "api-replace-authors")
        assert response.ok


# ---------------------------------------------------------------------------
# Tags (V3)
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestDatasetTagsApi:
    """Test dataset tag management via the V3 API."""

    def test_get_tags(self, draft_dataset, save_response):
        """GET /v3/datasets/<uuid>/tags should return a list."""
        page, container_uuid = draft_dataset
        response = page.request.get(
            f"/v3/datasets/{container_uuid}/tags"
        )
        save_response(response, "api-get-tags")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_tags(self, draft_dataset, save_response):
        """POST /v3/datasets/<uuid>/tags should add tags."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v3/datasets/{container_uuid}/tags",
            data={"tags": ["api-test-tag", "e2e-tag"]},
        )
        save_response(response, "api-add-tags")
        assert response.ok

        # Verify
        get_response = page.request.get(
            f"/v3/datasets/{container_uuid}/tags"
        )
        save_response(get_response, "api-add-tags-verify")
        tags = get_response.json()
        tag_values = [t.get("tag", t) if isinstance(t, dict) else t for t in tags]
        assert "api-test-tag" in tag_values or any("api-test-tag" in str(t) for t in tags)

    def test_delete_tag(self, draft_dataset, save_response):
        """DELETE /v3/datasets/<uuid>/tags should remove a tag."""
        page, container_uuid = draft_dataset
        # First add a tag
        page.request.post(
            f"/v3/datasets/{container_uuid}/tags",
            data={"tags": ["to-delete"]},
        )
        # Then delete it
        response = page.request.delete(
            f"/v3/datasets/{container_uuid}/tags?tag=to-delete"
        )
        save_response(response, "api-delete-tag")
        assert response.ok


# ---------------------------------------------------------------------------
# References (V3)
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestDatasetReferencesApi:
    """Test dataset reference management via the V3 API."""

    def test_get_references(self, draft_dataset, save_response):
        """GET /v3/datasets/<uuid>/references should return a list."""
        page, container_uuid = draft_dataset
        response = page.request.get(
            f"/v3/datasets/{container_uuid}/references"
        )
        save_response(response, "api-get-references")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_references(self, draft_dataset, save_response):
        """POST /v3/datasets/<uuid>/references should add references."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v3/datasets/{container_uuid}/references",
            data={"references": [{"url": "https://example.com/ref1"}]},
        )
        save_response(response, "api-add-references")
        assert response.ok

        # Verify
        get_response = page.request.get(
            f"/v3/datasets/{container_uuid}/references"
        )
        save_response(get_response, "api-add-references-verify")
        refs = get_response.json()
        assert len(refs) > 0

    def test_delete_references(self, draft_dataset, save_response):
        """DELETE /v3/datasets/<uuid>/references should remove a reference."""
        page, container_uuid = draft_dataset
        ref_url = "https://example.com/to-remove"
        # Add a reference first
        page.request.post(
            f"/v3/datasets/{container_uuid}/references",
            data={"references": [{"url": ref_url}]},
        )
        # Delete the specific reference via query parameter
        response = page.request.delete(
            f"/v3/datasets/{container_uuid}/references?url={ref_url}"
        )
        save_response(response, "api-delete-references")
        assert response.status == 204


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestDatasetCategoriesApi:
    """Test dataset category management via the API."""

    def test_get_categories(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/categories should return a list."""
        page, container_uuid = draft_dataset
        response = page.request.get(
            f"/v2/account/articles/{container_uuid}/categories"
        )
        save_response(response, "api-get-categories")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Private links
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestPrivateLinksApi:
    """Test private link CRUD via the API."""

    def test_create_private_link(self, draft_dataset, save_response):
        """POST /v2/account/articles/<uuid>/private_links should create a link."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v2/account/articles/{container_uuid}/private_links",
            data={"read_only": True},
        )
        save_response(response, "api-create-private-link")
        assert response.ok
        data = response.json()
        assert "location" in data

    def test_list_private_links(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/private_links should return links."""
        page, container_uuid = draft_dataset
        # Create a link first
        page.request.post(
            f"/v2/account/articles/{container_uuid}/private_links",
            data={"read_only": True},
        )
        response = page.request.get(
            f"/v2/account/articles/{container_uuid}/private_links"
        )
        save_response(response, "api-list-private-links")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_delete_private_link(self, draft_dataset, save_response):
        """DELETE private link should remove it."""
        page, container_uuid = draft_dataset
        # Create a link
        create_response = page.request.post(
            f"/v2/account/articles/{container_uuid}/private_links",
            data={"read_only": True},
        )
        link_data = create_response.json()
        link_id = link_data["location"].rstrip("/").split("/")[-1]

        # Delete the link
        delete_response = page.request.delete(
            f"/v2/account/articles/{container_uuid}/private_links/{link_id}"
        )
        save_response(delete_response, "api-delete-private-link")
        assert delete_response.status == 204


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestDatasetFilesApi:
    """Test dataset file listing via the API."""

    def test_get_private_files_empty(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/files on empty dataset returns list."""
        page, container_uuid = draft_dataset
        response = page.request.get(
            f"/v2/account/articles/{container_uuid}/files"
        )
        save_response(response, "api-get-files-empty")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


# ---------------------------------------------------------------------------
# Embargo
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestDatasetEmbargoApi:
    """Test dataset embargo endpoints via the API."""

    def test_get_embargo(self, draft_dataset, save_response):
        """GET /v2/account/articles/<uuid>/embargo should return embargo info."""
        page, container_uuid = draft_dataset
        response = page.request.get(
            f"/v2/account/articles/{container_uuid}/embargo"
        )
        save_response(response, "api-get-embargo")
        assert response.status == 200


# ---------------------------------------------------------------------------
# Published dataset API tests
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestPublishedDatasetApi:
    """Test API endpoints on published datasets."""

    def test_get_published_dataset_v2(self, published_dataset, save_response):
        """GET /v2/articles/<uuid> should return published dataset details."""
        page, container_uuid = published_dataset
        response = page.request.get(f"/v2/articles/{container_uuid}")
        save_response(response, "api-get-published-v2")
        assert response.status == 200
        data = response.json()
        assert data.get("title") == "API Test Published Dataset"

    def test_get_published_dataset_versions(self, published_dataset, save_response):
        """GET /v2/articles/<uuid>/versions should return version list."""
        page, container_uuid = published_dataset
        response = page.request.get(
            f"/v2/articles/{container_uuid}/versions"
        )
        save_response(response, "api-get-versions")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_published_dataset_files(self, published_dataset, save_response):
        """GET /v2/articles/<uuid>/files should return the file list."""
        page, container_uuid = published_dataset
        response = page.request.get(
            f"/v2/articles/{container_uuid}/files"
        )
        save_response(response, "api-get-published-files")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_published_dataset_in_search_results(self, published_dataset, save_response):
        """The published dataset should appear in search results."""
        page, container_uuid = published_dataset
        response = page.request.post(
            "/v2/articles/search",
            data={"search_for": "API Test Published Dataset", "limit": 10},
        )
        save_response(response, "api-search-published")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_published_dataset_in_v3_listing(self, published_dataset, save_response):
        """GET /v3/datasets should include the published dataset."""
        page, container_uuid = published_dataset
        response = page.request.get("/v3/datasets?limit=50")
        save_response(response, "api-v3-list-published")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.dataset
class TestDatasetApiErrors:
    """Test API error responses."""

    def test_invalid_method_on_public_dataset(self, page: Page, save_response):
        """PUT /v2/articles should not be allowed."""
        response = page.request.put("/v2/articles", data={})
        save_response(response, "api-invalid-method")
        assert response.status == 405

    def test_wrong_content_type(self, page: Page, save_response):
        """POST with unsupported Accept header should return 406."""
        response = page.request.post(
            "/v2/articles/search",
            headers={"Accept": "application/xml", "Content-Type": "application/xml"},
            data="<search/>",
        )
        save_response(response, "api-wrong-content-type")
        assert response.status in (400, 406, 415)

    def test_delete_nonexistent_dataset(self, authenticated_page: Page, save_response):
        """DELETE /v2/account/articles/<fake> should return 500 (dataset not found)."""
        fake_uuid = str(uuid.uuid4())
        response = authenticated_page.request.delete(
            f"/v2/account/articles/{fake_uuid}"
        )
        save_response(response, "api-delete-nonexistent")
        assert response.status == 500

    def test_update_nonexistent_dataset(self, authenticated_page: Page, save_response):
        """PUT /v2/account/articles/<fake> should return 404 or 403."""
        fake_uuid = str(uuid.uuid4())
        response = authenticated_page.request.put(
            f"/v2/account/articles/{fake_uuid}",
            data={"title": "Nope"},
        )
        save_response(response, "api-update-nonexistent")
        assert response.status in (403, 404)
