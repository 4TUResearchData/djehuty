"""
V3 Explore (SPARQL helper) API contract tests.

Endpoints (4):
    GET  /v3/explore/types
    GET  /v3/explore/properties
    GET  /v3/explore/property_value_types
    POST /v3/explore/clear-cache  (admin)

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_explore.py -v
"""

from playwright.sync_api import Page

from helpers.contract import assert_status


class TestV3ExploreApi:
    """V3 explore endpoints — RDF schema introspection."""

    def test_explore_types_requires_auth(self, page: Page, save_response):
        """GET /v3/explore/types without auth → 403."""
        response = page.request.get("/v3/explore/types")
        save_response(response, "v3-explore-types-no-auth")
        assert response.status in (401, 403)

    def test_explore_types_admin(self, admin_page: Page, save_response):
        """Admin GET /v3/explore/types → 200, JSON array."""
        response = admin_page.request.get("/v3/explore/types")
        save_response(response, "v3-explore-types")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_explore_properties_admin(self, admin_page: Page, save_response):
        """Admin GET /v3/explore/properties → 200, JSON array."""
        response = admin_page.request.get("/v3/explore/properties")
        save_response(response, "v3-explore-properties")
        assert_status(
            response,
            expected=200,
            current_bug=500,
            bug="#111: /v3/explore/properties returns 500 for admin",
        )
        if response.status == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_explore_property_value_types_admin(self, admin_page: Page, save_response):
        """Admin GET /v3/explore/property_value_types → 200, JSON array."""
        response = admin_page.request.get("/v3/explore/property_value_types")
        save_response(response, "v3-explore-property-value-types")
        assert_status(
            response,
            expected=200,
            current_bug=500,
            bug="#111: /v3/explore/property_value_types returns 500 for admin",
        )
        if response.status == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_explore_clear_cache_requires_admin(self, page: Page, save_response):
        """GET /v3/explore/clear-cache without auth → 403."""
        response = page.request.get("/v3/explore/clear-cache")
        save_response(response, "v3-explore-clear-cache-no-auth")
        assert response.status in (401, 403)

    def test_explore_clear_cache_admin(self, admin_page: Page, save_response):
        """Admin GET /v3/explore/clear-cache → 2xx."""
        response = admin_page.request.get("/v3/explore/clear-cache")
        save_response(response, "v3-explore-clear-cache")
        assert response.ok
