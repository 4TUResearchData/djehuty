"""Unit tests for the v2 API CORS policy (djehuty.application).

Pins the legacy-matching policy: any origin, all response headers exposed, no
credentials, and only Content-Type accepted as a request header.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app


class _Db:
    def __getattr__(self, name):
        return lambda *a, **k: []


def _client():
    return TestClient(create_app(_Db()))


def test_simple_request_exposes_all_headers_without_credentials():
    client = _client()
    response = client.get("/v2/articles", headers={"Origin": "https://example.org"})
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-expose-headers"] == "*"
    assert "access-control-allow-credentials" not in response.headers


def test_preflight_does_not_allow_authorization_header():
    client = _client()
    response = client.options(
        "/v2/articles",
        headers={
            "Origin": "https://example.org",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    allowed = response.headers.get("access-control-allow-headers", "")
    assert "authorization" not in allowed.lower()
