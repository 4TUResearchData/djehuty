"""
V2 Categories API contract tests.

Endpoints (1):
    GET   /v2/categories

Run with:
    cd tests/e2e && python -m pytest tests/api/v2/test_categories.py -v
"""

from playwright.sync_api import Page


class TestV2CategoriesApi:
    """Public /v2/categories endpoint."""

    def test_list_categories(self, page: Page, save_response):
        """GET /v2/categories → 200, JSON array of category records."""
        response = page.request.get("/v2/categories")
        save_response(response, "v2-list-categories")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        sample = data[0]
        assert "id" in sample or "category_id" in sample
        assert "title" in sample

    def test_categories_rejects_post(self, page: Page, save_response):
        """POST /v2/categories → 405 (read-only endpoint)."""
        response = page.request.post("/v2/categories", data={})
        save_response(response, "v2-categories-post-rejected")
        assert response.status == 405
