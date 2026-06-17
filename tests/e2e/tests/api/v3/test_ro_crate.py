"""
V3 RO-Crate API contract tests.

Endpoints (3):
    GET  /v3/ro-crates
    GET  /v3/datasets/<container_uuid>/ro-crate-metadata.json
    GET  /v3/datasets/<container_uuid>/versions/<version>/ro-crate-metadata.json

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_ro_crate.py -v
"""

import uuid

from playwright.sync_api import Page

from helpers.contract import assert_status


class TestV3RoCrateListApi:
    """GET /v3/ro-crates — published datasets as RO-Crate JSON-LD records."""

    def test_list_ro_crates(self, page: Page, save_response):
        """GET /v3/ro-crates → 200, JSON array."""
        response = page.request.get("/v3/ro-crates?limit=5")
        save_response(response, "v3-ro-crates")
        assert_status(
            response,
            expected=200,
            current_bug=500,
            bug="#111: /v3/ro-crates handler crashes on valid query",
        )
        if response.status == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_ro_crates_invalid_paging_400(self, page: Page, save_response):
        """GET /v3/ro-crates with invalid limit → 400."""
        response = page.request.get("/v3/ro-crates?limit=not-a-number")
        save_response(response, "v3-ro-crates-bad-limit")
        assert_status(
            response,
            expected=400,
            current_bug=500,
            bug="#111: /v3/ro-crates returns 500 instead of 400 for invalid limit",
        )


class TestV3DatasetRoCrateMetadataApi:
    """GET /v3/datasets/<uuid>/ro-crate-metadata.json — per-dataset RO-Crate."""

    def test_nonexistent_dataset_returns_404(self, page: Page, save_response):
        """GET on a fake container UUID → 404."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake_uuid}/ro-crate-metadata.json")
        save_response(response, "v3-ro-crate-metadata-404")
        assert response.status == 404

    def test_nonexistent_version_returns_404(self, page: Page, save_response):
        """GET on a fake (uuid, version) pair → 404."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.get(
            f"/v3/datasets/{fake_uuid}/versions/1/ro-crate-metadata.json"
        )
        save_response(response, "v3-ro-crate-version-metadata-404")
        assert response.status == 404
