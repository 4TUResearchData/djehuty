"""Unit tests for /v2/account/authors/search input validation.

Pins parity with legacy (wsgi.py api_private_authors_search): a missing
``search`` field is rejected with ``MissingRequiredField`` and legacy's message,
rather than a custom code.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app

AUTH = {"Authorization": "good"}


class _Db:
    def account_by_session_token(self, token):
        return {"uuid": "acct-1", "email": "x"} if token == "good" else None

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client():
    return TestClient(create_app(_Db()))


def test_authors_search_missing_field_is_a_400():
    response = _client().post("/v2/account/authors/search", json={}, headers=AUTH)
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "MissingRequiredField"
    assert body["message"] == "Missing required value for 'search'."


def test_authors_search_accepts_a_search_string():
    response = _client().post(
        "/v2/account/authors/search", json={"search": "Lovelace"}, headers=AUTH
    )
    assert response.status_code == 200
