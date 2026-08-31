"""Unit tests for the v2 API exception handlers (djehuty.api.exceptions).

Pins that a malformed JSON body reports a decode error rather than naming the
character offset as if it were a field.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app


class _Db:
    def __getattr__(self, name):
        return lambda *a, **k: []


def _client():
    return TestClient(create_app(_Db()))


def test_malformed_json_body_reports_a_decode_error():
    client = _client()
    response = client.post(
        "/v2/articles/search",
        content="{ not valid json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == 400
    assert body["message"].startswith("Failed to decode JSON object")
    assert "(char" in body["message"]
