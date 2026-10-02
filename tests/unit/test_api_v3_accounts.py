"""Unit tests for /v3/accounts/search.

The collaborator-autocomplete search must not disclose account e-mail
addresses (it would let any authenticated user enumerate the directory).
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app

AUTH = {"Authorization": "tok"}


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _Db:
    def __init__(self):
        self.cache = _Cache()

    def account_by_session_token(self, token):
        return {"uuid": "caller-1", "email": "caller@example.org"} if token == "tok" else None

    def accounts(self, search_for=None, limit=None):
        return [
            {
                "account_id": 1,
                "uuid": "u-1",
                "first_name": "Al",
                "last_name": "Ice",
                "full_name": "Al Ice",
                "email": "al.ice@example.org",
                "active": 1,
                "public": 0,
                "orcid_id": "",
            }
        ]

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client():
    db = _Db()
    return TestClient(create_app(db)), db


def test_accounts_search_omits_email():
    client, _ = _client()
    response = client.post(
        "/v3/accounts/search", json={"search_for": "al", "exclude": []}, headers=AUTH
    )
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all("email" not in row for row in rows)


def test_accounts_search_still_returns_identifying_fields():
    # The autocomplete needs uuid (to add) and full_name (to display).
    client, _ = _client()
    response = client.post(
        "/v3/accounts/search", json={"search_for": "al", "exclude": []}, headers=AUTH
    )
    rows = response.json()
    assert rows[0]["uuid"] == "u-1"
    assert rows[0]["full_name"] == "Al Ice"
