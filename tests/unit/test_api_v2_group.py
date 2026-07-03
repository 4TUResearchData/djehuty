"""The api-v2 group is registered and mounted (djehuty.route_groups + umbrella).

Verifies /v2/ resolves to the new stack, respects a legacy override, and that
the umbrella actually serves v2 endpoints. The AS-IS behaviour of the endpoints
themselves is covered by the e2e API contract suite (tests/e2e/tests/api/v2).
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app
from djehuty.route_groups import group_for_path, target_for_path


def test_v2_paths_resolve_to_new_by_default():
    assert group_for_path("/v2/articles").name == "api-v2"
    assert target_for_path("/v2/articles", default="new", overrides={}) == "new"


def test_v2_can_be_pinned_to_legacy():
    assert (
        target_for_path("/v2/articles", default="new", overrides={"api-v2": "legacy"}) == "legacy"
    )


def test_non_v2_path_is_not_owned_by_api_v2():
    # /v3/ has no group yet, so it resolves to legacy.
    assert group_for_path("/v3/datasets") is None
    assert target_for_path("/v3/datasets", default="new", overrides={}) == "legacy"


class _FakeDB:
    def account_by_session_token(self, token):
        return None

    def licenses(self):
        return [{"value": 1, "name": "CC0", "url": "https://creativecommons.org/"}]

    def __getattr__(self, name):
        return lambda *a, **k: []


def test_umbrella_mounts_v2_endpoints():
    client = TestClient(create_app(_FakeDB()))
    # A public v2 endpoint resolves (200), proving the router is mounted.
    assert client.get("/v2/licenses").status_code == 200


def test_authenticated_endpoints_document_the_token_header():
    spec = TestClient(create_app(_FakeDB())).get("/api/openapi.json").json()
    assert spec["components"]["securitySchemes"]["Session token"]["name"] == "Authorization"
    # An authenticated endpoint advertises the scheme; a public one does not.
    assert spec["paths"]["/v2/account"]["get"]["security"] == [{"Session token": []}]
    assert spec["paths"]["/v2/licenses"]["get"].get("security") is None


class _AuthDB(_FakeDB):
    def account_by_session_token(self, token):
        return {"uuid": "a1", "email": "x"} if token == "good" else None


def test_raw_and_prefixed_authorization_both_work():
    # AS-IS: legacy uses the raw Authorization value, stripping "token " only if
    # present. Swagger sends the raw token, so both forms must authenticate.
    client = TestClient(create_app(_AuthDB()))
    assert client.get("/v2/account", headers={"Authorization": "good"}).status_code == 200
    assert client.get("/v2/account", headers={"Authorization": "token good"}).status_code == 200
    assert client.get("/v2/account").status_code == 403
