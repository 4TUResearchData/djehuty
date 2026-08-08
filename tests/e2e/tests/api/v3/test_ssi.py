"""
V3 SSI (Self-Sovereign Identity) API contract tests.

Endpoints (2):
    PUT  /v3/receive-from-ssi
    GET  /v3/redirect-from-ssi/<container_uuid>/<token>

These endpoints are call-backs from an external SSI verifier. End-to-end
testing requires that verifier; dev and CI also run without `ssi_psk`
configured, so receive-from-ssi answers 404 before any method or body
handling. The tests pin that unconfigured behaviour.

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_ssi.py -v
"""

import uuid

from playwright.sync_api import Page


class TestV3ReceiveFromSsiApi:
    """PUT /v3/receive-from-ssi — SSI verifier callback.

    `ssi_psk` is unset in dev and CI, so the handler returns 404 before
    the method, psk, or body checks. A configured instance would answer
    405 to non-PUT and 403 to a wrong psk instead.
    """

    def test_unconfigured_get_returns_404(self, page: Page, save_response):
        """GET → 404 (ssi_psk unset; the method check is never reached)."""
        response = page.request.get("/v3/receive-from-ssi")
        save_response(response, "v3-receive-from-ssi-get")
        assert response.status == 404

    def test_unconfigured_put_returns_404(self, page: Page, save_response):
        """PUT with empty body → 404 (ssi_psk unset; the body is never read)."""
        response = page.request.put("/v3/receive-from-ssi", data={})
        save_response(response, "v3-receive-from-ssi-empty")
        assert response.status == 404


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
