"""Unit tests for the /v3/physical-samples/search endpoint."""

from fastapi.testclient import TestClient

from djehuty.application import create_app

BASE = "/v3/physical-samples/search"


class _Db:
    """Fake database with just the call the endpoint makes."""

    def __init__(self):
        self.search_calls = []

    def physical_samples(self, **kwargs):
        self.search_calls.append(kwargs)
        if kwargs.get("search_for") == "granite":
            return [{"container_uuid": "a1111111-1111-4111-8111-111111111111", "title": "Granite"}]
        return []


def _client(db=None):
    """Build a test client around DB, or a fresh fake, and return both."""
    db = db or _Db()
    return TestClient(create_app(db)), db


def test_returns_matching_samples():
    """A matching search term returns the formatted sample."""
    client, db = _client()
    response = client.post(BASE, json={"search_for": "granite"})
    assert response.status_code == 200
    assert response.json() == [
        {"uuid": "a1111111-1111-4111-8111-111111111111", "title": "Granite"}
    ]
    assert db.search_calls[-1]["search_for"] == "granite"
    assert db.search_calls[-1]["is_published"] is True
    assert db.search_calls[-1]["is_latest"] is True


def test_is_empty_without_a_match():
    """A search term with no match returns an empty list."""
    client, _ = _client()
    response = client.post(BASE, json={"search_for": "basalt"})
    assert response.status_code == 200
    assert response.json() == []


def test_missing_search_for_is_a_400():
    """A body without 'search_for' is a 400."""
    client, db = _client()
    response = client.post(BASE, json={})
    assert response.status_code == 400
    assert db.search_calls == []


def test_an_empty_search_for_is_a_400():
    """An empty 'search_for' is a 400."""
    client, db = _client()
    response = client.post(BASE, json={"search_for": ""})
    assert response.status_code == 400
    assert db.search_calls == []


def test_does_not_require_a_session():
    """The search endpoint is public and needs no authentication."""
    client, _ = _client()
    response = client.post(BASE, json={"search_for": "granite"})
    assert response.status_code == 200
