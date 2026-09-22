"""The umbrella app serves its OpenAPI docs."""

from fastapi.testclient import TestClient

from djehuty.application import create_app


class _DB:
    def account_by_session_token(self, token):
        return None


def test_umbrella_serves_openapi_docs():
    client = TestClient(create_app(_DB()))
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200
