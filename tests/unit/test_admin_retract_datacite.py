"""Unit tests for the DataCite requests made after an admin retract.

requests.put is mocked, so these prove the requests we build, not that DataCite accepts them."""

import base64
import json
import logging
from types import SimpleNamespace

import pytest
import requests

from djehuty.web import database
from djehuty.web.config import config
from djehuty.web.wsgi import WebServer

CONTAINER = "a4b15000-0009-4000-8000-010000000000"
CONTAINER_DOI = "10.4121/x"
VERSION_DOIS = {1: "10.4121/x.v1", 2: "10.4121/x.v2", 3: "10.4121/x.v3"}
VERSION_UUIDS = {
    1: "a4b15000-0009-4000-8000-020000000001",
    2: "a4b15000-0009-4000-8000-020000000002",
}
BASE_URL = "https://data.test"


def _version(number):
    return {"version": number, "uuid": VERSION_UUIDS.get(number, str(number))}


def _plan(selected, remaining):
    return {
        "selected": [_version(number) for number in selected],
        "remaining": [_version(number) for number in remaining],
        "latest": _version(max(selected + remaining)),
        "retracts_latest": max(selected + remaining) in selected,
    }


def _parameters(doi, version):
    return {
        "doi": doi,
        "item": {"title": "Penguins", "version": version, "description": "Text"},
        "published_date": "2026-04-0%d" % version,
        "published_year": "2026",
    }


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.text = "body"


class Puts(list):
    """The recorded PUTs, plus the status code the fake DataCite answers with."""

    status = None


@pytest.fixture
def puts(monkeypatch):
    """Records every requests.put as (doi, attributes)."""
    recorded = Puts()
    status = {"code": 200}

    def fake_put(url, json=None, **_):
        recorded.append((url.rsplit("/dois/", 1)[1], json["data"]["attributes"]))
        return FakeResponse(status["code"])

    monkeypatch.setattr(requests, "put", fake_put)
    recorded.status = status
    return recorded


@pytest.fixture
def settings(monkeypatch):
    for name, value in {
        "in_production": True,
        "in_preproduction": False,
        "datacite_url": "https://datacite.test",
        "datacite_id": "id",
        "datacite_password": "password",
        "base_url": BASE_URL,
        "site_name": "test",
    }.items():
        monkeypatch.setattr(config, name, value, raising=False)


@pytest.fixture
def server(settings, monkeypatch):
    instance = WebServer.__new__(WebServer)
    instance.log = logging.getLogger("test-retract-datacite")
    instance.db = SimpleNamespace(container=lambda uuid: {"doi": CONTAINER_DOI})

    def export(container_uuid, version=None, item_type="dataset", from_draft=False):
        doi = VERSION_DOIS[version or 3]
        return _parameters(doi, version or 3)

    monkeypatch.setattr(instance, "_WebServer__metadata_export_parameters", export, raising=False)
    return instance


def _decoded_xml(attributes):
    return base64.b64decode(attributes["xml"]).decode("utf-8")


def _sync(server, snapshot_versions, plan):
    snapshot = server._WebServer__retract_snapshot(CONTAINER, plan)
    assert sorted(snapshot) == sorted(snapshot_versions)
    return server._WebServer__sync_datacite_after_retract(CONTAINER, snapshot, plan)


class TestSyncAfterRetract:
    def test_retract_subset_hides_only_selected_dois(self, server, puts):
        plan = _plan(selected=[1], remaining=[2, 3])
        _sync(server, [1], plan)

        hidden = [(doi, a["event"]) for doi, a in puts if a["event"] == "hide"]
        assert hidden == [(VERSION_DOIS[1], "hide")]

    def test_hide_sends_tombstone_url_and_withdrawn_date(self, server, puts):
        _sync(server, [1], _plan(selected=[1], remaining=[2, 3]))

        doi, attributes = puts[0]
        assert doi == VERSION_DOIS[1]
        assert attributes["url"] == f"{BASE_URL}/datasets/{CONTAINER}/1"
        xml = _decoded_xml(attributes)
        assert 'dateType="Withdrawn"' in xml
        assert 'dateInformation="Retracted by the repository administrators."' in xml
        assert 'dateType="Issued"' in xml

    def test_container_doi_refreshed_when_versions_remain(self, server, puts):
        _sync(server, [1], _plan(selected=[1], remaining=[2, 3]))

        container_puts = [(doi, a) for doi, a in puts if doi == CONTAINER_DOI]
        assert len(container_puts) == 1
        attributes = container_puts[0][1]
        assert attributes["event"] == "publish"
        assert attributes["url"] == f"{BASE_URL}/datasets/{CONTAINER}"
        xml = _decoded_xml(attributes)
        assert f">{CONTAINER_DOI}</identifier>" in xml
        assert "Withdrawn" not in xml

    def test_container_doi_hidden_when_everything_is_retracted(self, server, puts):
        _sync(server, [1, 2, 3], _plan(selected=[1, 2, 3], remaining=[]))

        container_puts = [a for doi, a in puts if doi == CONTAINER_DOI]
        assert [a["event"] for a in container_puts] == ["hide"]
        assert container_puts[0]["url"] == f"{BASE_URL}/datasets/{CONTAINER}"
        assert f">{CONTAINER_DOI}</identifier>" in _decoded_xml(container_puts[0])

    def test_failures_become_warnings(self, server, puts):
        puts.status["code"] = 500
        warnings = _sync(server, [1], _plan(selected=[1], remaining=[2, 3]))

        assert warnings == [
            f"DataCite: could not hide {VERSION_DOIS[1]}.",
            f"DataCite: could not update {CONTAINER_DOI}.",
        ]

    def test_failure_is_logged_for_replay(self, server, puts, caplog):
        puts.status["code"] = 500
        with caplog.at_level(logging.ERROR, logger="test-retract-datacite"):
            _sync(server, [1], _plan(selected=[1], remaining=[2, 3]))

        assert (
            f"doi={VERSION_DOIS[1]} event=hide url={BASE_URL}/datasets/{CONTAINER}/1" in caplog.text
        )

    def test_connection_error_is_a_warning(self, server, monkeypatch):
        def refuse(*_, **__):
            raise requests.exceptions.ConnectionError

        monkeypatch.setattr(requests, "put", refuse)
        warnings = _sync(server, [1], _plan(selected=[1], remaining=[2, 3]))

        assert warnings[0] == f"DataCite: could not hide {VERSION_DOIS[1]}."

    def test_versions_without_a_doi_are_skipped(self, server, puts, monkeypatch):
        monkeypatch.setattr(
            server,
            "_WebServer__metadata_export_parameters",
            lambda *args, **kwargs: {"item": {"title": "t"}},
            raising=False,
        )
        snapshot = server._WebServer__retract_snapshot(
            CONTAINER, _plan(selected=[1], remaining=[2])
        )
        assert snapshot == {}


class FakeRequest:
    method = "PUT"

    def get_json(self):
        return {
            "container_uuid": CONTAINER,
            "confirm_doi": CONTAINER_DOI,
            "expected_doi": CONTAINER_DOI,
            "version_uuids": [VERSION_UUIDS[1]],
        }


def _execute(server, plan, success=True):
    calls = []
    server.token_from_cookie = lambda request: "token"
    server.default_error_handling = lambda *args: None
    server.db.may_administer = lambda token: True
    server.db.account_by_session_token = lambda token: {"uuid": "a"}
    server.db.plan_retract = lambda container, versions: plan
    server.db.admin_retract_dataset = lambda *args, **kwargs: calls.append("retract") or success
    return WebServer.api_admin_retract_execute(server, FakeRequest()), calls


class TestExecuteEndpoint:
    def test_datacite_failure_does_not_undo_the_retract(self, server, puts):
        puts.status["code"] = 500
        response, calls = _execute(server, _plan(selected=[1], remaining=[2, 3]))

        assert calls == ["retract"]
        assert response.status_code == 200
        assert json.loads(response.get_data())["warnings"]

    def test_success_without_warnings_is_204(self, server, puts):
        response, _ = _execute(server, _plan(selected=[1], remaining=[2, 3]))
        assert response.status_code == 204

    def test_not_called_outside_production(self, server, puts, monkeypatch):
        monkeypatch.setattr(config, "in_production", False)
        snapshots = []
        monkeypatch.setattr(
            server,
            "_WebServer__retract_snapshot",
            lambda *args: snapshots.append(args),
            raising=False,
        )

        response, calls = _execute(server, _plan(selected=[1], remaining=[2, 3]))

        assert response.status_code == 204
        assert calls == ["retract"]
        assert puts == []
        assert snapshots == []

    def test_preproduction_is_not_called(self, server, puts, monkeypatch):
        monkeypatch.setattr(config, "in_preproduction", True)
        response, _ = _execute(server, _plan(selected=[1], remaining=[2, 3]))
        assert response.status_code == 204
        assert puts == []

    def test_refused_retract_never_reaches_datacite(self, server, puts):
        def refuse(container, versions):
            raise database.RetractRefused("DraftExists", "draft")

        server.error_400 = lambda request, message, code: SimpleNamespace(status_code=400)
        server.db.plan_retract = refuse
        server.token_from_cookie = lambda request: "token"
        server.default_error_handling = lambda *args: None
        server.db.may_administer = lambda token: True
        server.db.account_by_session_token = lambda token: {"uuid": "a"}

        response = WebServer.api_admin_retract_execute(server, FakeRequest())

        assert response.status_code == 400
        assert puts == []
