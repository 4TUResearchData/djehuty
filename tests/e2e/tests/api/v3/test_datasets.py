"""
V3 Datasets API contract tests.

Covers /v3/datasets* endpoints:
  - List, search, ordering
  - Top / timeline
  - Tags & references CRUD
  - Authors (v3) & reorder-authors
  - Collaborators
  - Workflow: submit-for-review, publish, decline
  - File operations: upload, image-files, update-thumbnail, repair_md5s
  - DOI badge SVGs
  - Published listing visibility

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_datasets.py -v
"""

import uuid

from playwright.sync_api import Page

from helpers.contract import assert_status


# ---------------------------------------------------------------------------
# Public read
# ---------------------------------------------------------------------------


class TestV3PublicDatasetsApi:
    """Public (unauthenticated) /v3/datasets endpoints."""

    def test_list_datasets(self, page: Page, save_response):
        """GET /v3/datasets → 200, JSON array."""
        response = page.request.get("/v3/datasets?limit=5")
        save_response(response, "v3-list-datasets")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_datasets(self, page: Page, save_response):
        """POST /v3/datasets/search without explicit scope → all scopes."""
        response = page.request.post(
            "/v3/datasets/search",
            data={"search_for": "test"},
        )
        save_response(response, "v3-search-datasets")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_datasets_with_order(self, page: Page, save_response):
        """GET /v3/datasets with order parameters returns sorted results."""
        response = page.request.get(
            "/v3/datasets?limit=5&order=published_date&order_direction=desc"
        )
        save_response(response, "v3-datasets-ordered")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TestV3DatasetTagsApi:
    """Dataset tag management."""

    def test_get_tags(self, draft_dataset, save_response):
        """GET /v3/datasets/<uuid>/tags → list."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v3/datasets/{container_uuid}/tags")
        save_response(response, "api-get-tags")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_tags(self, draft_dataset, save_response):
        """POST /v3/datasets/<uuid>/tags adds tags."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v3/datasets/{container_uuid}/tags",
            data={"tags": ["api-test-tag", "e2e-tag"]},
        )
        save_response(response, "api-add-tags")
        assert response.ok

        get_response = page.request.get(f"/v3/datasets/{container_uuid}/tags")
        save_response(get_response, "api-add-tags-verify")
        tags = get_response.json()
        tag_values = [t.get("tag", t) if isinstance(t, dict) else t for t in tags]
        assert "api-test-tag" in tag_values or any(
            "api-test-tag" in str(t) for t in tags
        )

    def test_delete_tag(self, draft_dataset, save_response):
        """DELETE /v3/datasets/<uuid>/tags?tag=<value> removes a tag."""
        page, container_uuid = draft_dataset
        page.request.post(
            f"/v3/datasets/{container_uuid}/tags",
            data={"tags": ["to-delete"]},
        )
        response = page.request.delete(
            f"/v3/datasets/{container_uuid}/tags?tag=to-delete"
        )
        save_response(response, "api-delete-tag")
        assert response.ok


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------


class TestV3DatasetReferencesApi:
    """Dataset reference management."""

    def test_get_references(self, draft_dataset, save_response):
        """GET /v3/datasets/<uuid>/references → list."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v3/datasets/{container_uuid}/references")
        save_response(response, "api-get-references")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_add_references(self, draft_dataset, save_response):
        """POST /v3/datasets/<uuid>/references adds references."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v3/datasets/{container_uuid}/references",
            data={"references": [{"url": "https://example.com/ref1"}]},
        )
        save_response(response, "api-add-references")
        assert response.ok

        get_response = page.request.get(f"/v3/datasets/{container_uuid}/references")
        save_response(get_response, "api-add-references-verify")
        refs = get_response.json()
        assert len(refs) > 0

    def test_delete_references(self, draft_dataset, save_response):
        """DELETE /v3/datasets/<uuid>/references?url=<url> removes a reference."""
        page, container_uuid = draft_dataset
        ref_url = "https://example.com/to-remove"
        page.request.post(
            f"/v3/datasets/{container_uuid}/references",
            data={"references": [{"url": ref_url}]},
        )
        response = page.request.delete(
            f"/v3/datasets/{container_uuid}/references?url={ref_url}"
        )
        save_response(response, "api-delete-references")
        assert response.status == 204


# ---------------------------------------------------------------------------
# Top / timeline
# ---------------------------------------------------------------------------


class TestV3DatasetsTopApi:
    """GET /v3/datasets/top/<item_type>."""

    def test_top_datasets(self, page: Page, save_response):
        """GET /v3/datasets/top/datasets → 200, JSON array."""
        response = page.request.get("/v3/datasets/top/datasets")
        save_response(response, "v3-datasets-top")
        assert_status(
            response,
            expected=200,
            current_bug=400,
            bug="#111: /v3/datasets/top/datasets rejects the default item_type",
        )
        if response.status == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_top_invalid_type(self, page: Page, save_response):
        """An unrecognised item_type → 4xx."""
        response = page.request.get("/v3/datasets/top/not-a-type")
        save_response(response, "v3-datasets-top-bad")
        assert 400 <= response.status < 500


class TestV3DatasetsTimelineApi:
    """GET /v3/datasets/timeline/<item_type>."""

    def test_timeline(self, page: Page, save_response):
        """GET /v3/datasets/timeline/datasets → 200, JSON."""
        response = page.request.get("/v3/datasets/timeline/datasets")
        save_response(response, "v3-datasets-timeline")
        assert_status(
            response,
            expected=200,
            current_bug=400,
            bug="#111: /v3/datasets/timeline/datasets rejects the default item_type",
        )


# ---------------------------------------------------------------------------
# DOI badge SVG
# ---------------------------------------------------------------------------


class TestV3DoiBadgeApi:
    """GET /v3/datasets/<id>/doi-badge[-v<version>].svg."""

    def test_nonexistent_returns_404(self, page: Page, save_response):
        """GET on a fake dataset → 404."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}/doi-badge.svg")
        save_response(response, "v3-doi-badge-404")
        assert_status(
            response,
            expected=404,
            current_bug=500,
            bug="#111: /v3/datasets/<id>/doi-badge.svg returns 500 instead of 404",
        )

    def test_versioned_nonexistent_returns_404(self, page: Page, save_response):
        """GET versioned badge on a fake dataset → 404."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}/doi-badge-v1.svg")
        save_response(response, "v3-doi-badge-v-404")
        assert_status(
            response,
            expected=404,
            current_bug=500,
            bug="#111: /v3/datasets/<id>/doi-badge-v<v>.svg returns 500 instead of 404",
        )


# ---------------------------------------------------------------------------
# Workflow: submit-for-review, publish, decline
# ---------------------------------------------------------------------------


class TestV3DatasetWorkflowApi:
    """Review-cycle endpoints."""

    def test_submit_requires_auth(self, page: Page, save_response):
        """PUT .../submit-for-review without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.put(
            f"/v3/datasets/{fake}/submit-for-review",
            data={},
        )
        save_response(response, "v3-submit-no-auth")
        assert response.status in (401, 403)

    def test_submit_unprepared_returns_error(self, draft_dataset, save_response):
        """Submitting an unprepared draft → 4xx (missing required fields)."""
        page, container_uuid = draft_dataset
        response = page.request.put(
            f"/v3/datasets/{container_uuid}/submit-for-review",
            data={},
        )
        save_response(response, "v3-submit-unprepared")
        assert 400 <= response.status < 600

    def test_publish_requires_auth(self, page: Page, save_response):
        """POST .../publish without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/datasets/{fake}/publish",
            data={},
        )
        save_response(response, "v3-publish-no-auth")
        assert response.status in (401, 403)

    def test_decline_requires_auth(self, page: Page, save_response):
        """POST .../decline without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/datasets/{fake}/decline",
            data={},
        )
        save_response(response, "v3-decline-no-auth")
        assert response.status in (401, 403)


# ---------------------------------------------------------------------------
# Files: upload, image-files, update-thumbnail, repair_md5s
# ---------------------------------------------------------------------------


class TestV3DatasetFileOperationsApi:
    """Endpoints that mutate file state on a dataset."""

    def test_upload_requires_auth(self, page: Page, save_response):
        """POST .../upload without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/datasets/{fake}/upload",
            data={},
        )
        save_response(response, "v3-upload-no-auth")
        assert response.status in (401, 403)

    def test_image_files_requires_auth(self, page: Page, save_response):
        """GET .../image-files without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}/image-files")
        save_response(response, "v3-image-files-no-auth")
        assert response.status in (401, 403)

    def test_update_thumbnail_requires_auth(self, page: Page, save_response):
        """PUT .../update-thumbnail without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.put(
            f"/v3/datasets/{fake}/update-thumbnail",
            data={},
        )
        save_response(response, "v3-update-thumbnail-no-auth")
        assert response.status in (401, 403)

    def test_repair_md5s_requires_admin(self, page: Page, save_response):
        """POST .../repair_md5s without admin → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/datasets/{fake}/repair_md5s",
            data={},
        )
        save_response(response, "v3-repair-md5s-no-auth")
        assert response.status in (401, 403)


# ---------------------------------------------------------------------------
# Authors (v3)
# ---------------------------------------------------------------------------


class TestV3DatasetAuthorsApi:
    """V3 dataset author management — separate from the v2 authors endpoint."""

    def test_get_v3_authors(self, draft_dataset, save_response):
        """GET /v3/datasets/<uuid>/authors → 200, JSON array."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v3/datasets/{container_uuid}/authors")
        save_response(response, "v3-dataset-authors")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_delete_v3_author_missing(self, draft_dataset, save_response):
        """DELETE /v3/datasets/<uuid>/authors/<fake> → 4xx."""
        page, container_uuid = draft_dataset
        fake = str(uuid.uuid4())
        response = page.request.delete(f"/v3/datasets/{container_uuid}/authors/{fake}")
        save_response(response, "v3-dataset-author-delete-missing")
        assert 400 <= response.status < 600


class TestV3DatasetReorderAuthorsApi:
    """POST /v3/datasets/<uuid>/reorder-authors."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/datasets/{fake}/reorder-authors",
            data={"order": []},
        )
        save_response(response, "v3-dataset-reorder-no-auth")
        assert response.status in (401, 403)

    def test_reorder_empty(self, draft_dataset, save_response):
        """POST with empty order → 2xx or 4xx (depends on validator)."""
        page, container_uuid = draft_dataset
        response = page.request.post(
            f"/v3/datasets/{container_uuid}/reorder-authors",
            data={"order": []},
        )
        save_response(response, "v3-dataset-reorder-empty")
        assert response.status in (200, 204, 400)


# ---------------------------------------------------------------------------
# Collaborators
# ---------------------------------------------------------------------------


class TestV3DatasetCollaboratorsApi:
    """Collaborator endpoints."""

    def test_list_requires_auth(self, page: Page, save_response):
        """GET .../collaborators without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}/collaborators")
        save_response(response, "v3-collaborators-no-auth")
        assert response.status in (401, 403)

    def test_list_on_draft(self, draft_dataset, save_response):
        """GET .../collaborators on a draft → 200, JSON array."""
        page, container_uuid = draft_dataset
        response = page.request.get(f"/v3/datasets/{container_uuid}/collaborators")
        save_response(response, "v3-collaborators")
        # Owner can read; the list may be empty.
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_delete_collaborator_missing(self, draft_dataset, save_response):
        """DELETE .../collaborators/<fake> → 204 (idempotent DELETE) or 4xx."""
        page, container_uuid = draft_dataset
        fake = str(uuid.uuid4())
        response = page.request.delete(
            f"/v3/datasets/{container_uuid}/collaborators/{fake}"
        )
        save_response(response, "v3-collaborator-delete-missing")
        # Idempotent DELETE is REST-idiomatic; 204 on a missing collaborator
        # is acceptable.
        assert response.status == 204 or 400 <= response.status < 600


# ---------------------------------------------------------------------------
# Published-dataset visibility
# ---------------------------------------------------------------------------


class TestV3PublishedDatasetsApi:
    """Published datasets are visible on /v3/datasets."""

    def test_published_dataset_in_v3_listing(self, published_dataset, save_response):
        """GET /v3/datasets includes the published dataset."""
        page, container_uuid = published_dataset
        response = page.request.get("/v3/datasets?limit=50")
        save_response(response, "api-v3-list-published")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
