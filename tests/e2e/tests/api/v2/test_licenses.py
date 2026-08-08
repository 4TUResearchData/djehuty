"""
V2 Licenses API contract tests.

Endpoints (1):
    GET   /v2/licenses

Run with:
    cd tests/e2e && python -m pytest tests/api/v2/test_licenses.py -v
"""

from playwright.sync_api import Page


class TestV2LicensesApi:
    """Public /v2/licenses endpoint."""

    def test_list_licenses(self, page: Page, save_response):
        """GET /v2/licenses → 200, JSON array of license records."""
        response = page.request.get("/v2/licenses")
        save_response(response, "v2-list-licenses")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        sample = data[0]
        assert "value" in sample
        assert "name" in sample

    def test_licenses_rejects_post(self, page: Page, save_response):
        """POST /v2/licenses → 405 (read-only endpoint)."""
        response = page.request.post("/v2/licenses", data={})
        save_response(response, "v2-licenses-post-rejected")
        assert response.status == 405
