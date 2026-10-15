"""Unit tests for /v2/account/articles/{id}/categories input validation.

Pins parity with legacy: a missing ``categories`` key is rejected with
``NoCategoriesField`` and a null value with ``MissingRequiredField``, rather
than silently succeeding.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app

DATASET_UUID = "a" * 36
AUTH = {"Authorization": "good"}


class _Db:
    def account_by_session_token(self, token):
        return {"uuid": "acct-1", "email": "x"} if token == "good" else None

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client():
    return TestClient(create_app(_Db()))


def test_put_categories_without_key_is_a_400():
    client = _client()
    response = client.put(f"/v2/account/articles/{DATASET_UUID}/categories", json={}, headers=AUTH)
    assert response.status_code == 400
    assert response.json()["code"] == "NoCategoriesField"


def test_put_categories_null_is_a_400():
    client = _client()
    response = client.put(
        f"/v2/account/articles/{DATASET_UUID}/categories",
        json={"categories": None},
        headers=AUTH,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "MissingRequiredField"
