"""Unit tests for the public /v2/articles search endpoint (djehuty.api.v2).

Pins that POST /v2/articles/search counts matches the same way it lists them:
the row query and the count query use the same ``is_latest`` filter, so the
``Number-Of-Records`` total agrees with the rows returned (legacy: 10/10).
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app

CONTAINER_UUID = "c" * 36


class _Db:
    def __init__(self):
        self.dataset_calls = []

    def datasets(self, **kwargs):
        self.dataset_calls.append(kwargs)
        # The count query differentiates itself with return_count=True. It must
        # honour the same is_latest filter as the row query below: latest-only
        # would see a single version, all-versions sees both.
        if kwargs.get("return_count"):
            return [{"datasets": 1 if kwargs.get("is_latest") else 2}]
        if kwargs.get("is_latest"):
            return [{"uri": "dataset:v2", "container_uuid": CONTAINER_UUID}]
        return [
            {"uri": "dataset:v1", "container_uuid": CONTAINER_UUID},
            {"uri": "dataset:v2", "container_uuid": CONTAINER_UUID},
        ]

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client(db=None):
    db = db or _Db()
    return TestClient(create_app(db)), db


def test_search_articles_count_matches_returned_rows_across_versions():
    client, db = _client()
    response = client.post("/v2/articles/search", json={"search_for": "djehuty"})
    assert response.status_code == 200
    assert len(response.json()) == 2

    row_call = next(c for c in db.dataset_calls if not c.get("return_count"))
    count_call = next(c for c in db.dataset_calls if c.get("return_count"))
    assert row_call["is_latest"] is False
    assert count_call["is_latest"] is False

    assert response.headers["Number-Of-Records"] == "2"
    assert response.headers["Number-Of-Returned-Records"] == "2"
