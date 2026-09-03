"""Unit tests for the public /v2/collections endpoints (djehuty.api.v2).

Pins that GET /v2/collections/{id}/articles resolves the collection and lists
its datasets by the collection URI, and returns 404 for an unknown collection.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app

COLLECTION_UUID = "a" * 36
DATASET_UUID = "b" * 36


class _Db:
    def __init__(self):
        self.dataset_calls = []

    def collections(self, **kwargs):
        return [{"uri": "collection:col-1", "container_uuid": COLLECTION_UUID}]

    def datasets(self, **kwargs):
        self.dataset_calls.append(kwargs)
        return [{"container_uuid": DATASET_UUID}]

    def __getattr__(self, name):
        return lambda *a, **k: []


class _EmptyDb(_Db):
    def collections(self, **kwargs):
        return []


def _client(db=None):
    db = db or _Db()
    return TestClient(create_app(db)), db


def test_public_collection_articles_lists_by_collection_uri():
    client, db = _client()
    response = client.get(f"/v2/collections/{COLLECTION_UUID}/articles")
    assert response.status_code == 200
    assert len(response.json()) == 1
    call = db.dataset_calls[-1]
    assert call["collection_uri"] == "collection:col-1"
    assert call["is_latest"] is True


def test_public_collection_articles_unknown_is_404():
    client, _ = _client(_EmptyDb())
    response = client.get(f"/v2/collections/{COLLECTION_UUID}/articles")
    assert response.status_code == 404
