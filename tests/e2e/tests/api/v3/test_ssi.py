"""
V3 SSI (Self-Sovereign Identity) API contract tests.

Endpoints (2):
    POST /v3/receive-from-ssi
    GET  /v3/redirect-from-ssi/<container_uuid>/<token>

These endpoints are call-backs from an external SSI verifier. End-to-end
testing requires that verifier; here we only assert the routes reject
malformed requests in the expected way.

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_ssi.py -v
"""

import uuid

from playwright.sync_api import Page


class TestV3ReceiveFromSsiApi:
    """POST /v3/receive-from-ssi — SSI verifier callback."""

    def test_rejects_get(self, page: Page, save_response):
        """GET → 4xx (the route only accepts POST)."""
        response = page.request.get("/v3/receive-from-ssi")
        save_response(response, "v3-receive-from-ssi-get")
        assert 400 <= response.status < 500

    def test_empty_post_returns_error(self, page: Page, save_response):
        """POST with empty body → 4xx (no SSI payload to verify)."""
        response = page.request.post("/v3/receive-from-ssi", data={})
        save_response(response, "v3-receive-from-ssi-empty")
        assert 400 <= response.status < 500


class TestV3RedirectFromSsiApi:
    """GET /v3/redirect-from-ssi/<container_uuid>/<token>."""

    def test_invalid_uuid_returns_403(self, page: Page, save_response):
        """Container UUID that isn't a valid UUID → 403."""
        response = page.request.get(
            "/v3/redirect-from-ssi/not-a-uuid/sometoken",
        )
        save_response(response, "v3-redirect-from-ssi-bad-uuid")
        assert response.status == 403

    def test_rejects_post(self, page: Page, save_response):
        """POST → 405 (GET-only route)."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/redirect-from-ssi/{fake}/sometoken",
            data={},
        )
        save_response(response, "v3-redirect-from-ssi-post")
        assert response.status == 405
