"""Unit tests for the DataCite records behind an administrator's licence change.

Pins the behaviour of /admin/update-published-dataset/license/update: a
published dataset has a container DOI and a version DOI.
"""

import json
import logging

import requests
from werkzeug.test import Client

from djehuty.utils import convenience
from djehuty.web import wsgi as wsgi_module
from djehuty.web.config import config
from djehuty.web.wsgi import WebServer

convenience.add_logging_level("ACCESS", logging.INFO + 5)
convenience.add_logging_level("AUDIT", logging.INFO + 6)

CONTAINER_UUID = "f0e1d2c3-b4a5-6789-a123-456789abcdef"
DATASET_UUID = "a1b2c3d4-e5f6-7890-b234-567890abcdef"
CONTAINER_DOI = f"10.4121/{CONTAINER_UUID}"
OLD_LICENSE = "https://creativecommons.org/licenses/by/4.0/"
NEW_LICENSE = "https://creativecommons.org/publicdomain/zero/1.0/"

CONTAINER_TARGET = (None, CONTAINER_DOI)
VERSION_TARGET = (2, None)


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _Db:
    """Records the licence writes it is asked to make, in order."""

    def __init__(self, events):
        self.cache = _Cache()
        self.events = events
        self.revert_fails = False

    def may_administer(self, token, account=None):
        return token == "admin-token"

    def account_by_session_token(self, token):
        return {"uuid": "admin-1"}

    def licenses(self):
        return [{"url": OLD_LICENSE}, {"url": NEW_LICENSE}]

    def datasets(self, **kwargs):
        if kwargs.get("is_latest") and kwargs.get("dataset_uuid") == DATASET_UUID:
            return [
                {
                    "uuid": DATASET_UUID,
                    "license_url": OLD_LICENSE,
                    "version": 2,
                    "container_doi": CONTAINER_DOI,
                    "account_uuid": "owner-1",
                }
            ]
        return []

    def admin_update_license(self, container_uuid, dataset_uuid, url, admin_uuid, **kwargs):
        if self.revert_fails and any(event[0] == "db" for event in self.events):
            return False
        self.events.append(("db", url))
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _server(monkeypatch, in_production=True, doi_plan=None, revert_fails=False):
    """Build a client whose DOI sends are recorded instead of performed.

    DOI_PLAN(target, attempt) decides whether DataCite accepts a send; the
    attempt counter separates a first send from a re-send of the same record.
    """
    events = []
    server = WebServer()
    server.db = _Db(events)
    server.db.revert_fails = revert_fails
    monkeypatch.setattr(config, "in_production", in_production)
    monkeypatch.setattr(config, "in_preproduction", False)

    def fake_send(self, item_id, **kwargs):
        target = (kwargs.get("version"), kwargs.get("doi"))
        attempt = sum(1 for event in events if event == ("doi", target)) + 1
        events.append(("doi", target))
        return True if doi_plan is None else doi_plan(target, attempt)

    monkeypatch.setattr(WebServer, "_WebServer__update_item_doi", fake_send)
    client = Client(server)
    client.set_cookie("djehuty_session", "admin-token", domain="localhost")
    return client, events


def _update_license(client):
    return client.put(
        "/admin/update-published-dataset/license/update",
        data=json.dumps(
            {
                "container_uuid": CONTAINER_UUID,
                "dataset_uuid": DATASET_UUID,
                "new_license_url": NEW_LICENSE,
            }
        ),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )


def test_both_doi_records_are_sent(monkeypatch):
    """The container record first, because it is the one the approval mail cites."""
    client, events = _server(monkeypatch)
    assert _update_license(client).status_code == 204
    assert events == [
        ("db", NEW_LICENSE),
        ("doi", CONTAINER_TARGET),
        ("doi", VERSION_TARGET),
    ]


def test_datacite_is_untouched_outside_production(monkeypatch):
    client, events = _server(monkeypatch, in_production=False)
    assert _update_license(client).status_code == 204
    assert events == [("db", NEW_LICENSE)]


def test_accepted_record_is_resent_after_the_revert(monkeypatch):
    """Container accepted, version refused. Reverting the database alone would
    leave the container record stating the new licence."""
    client, events = _server(
        monkeypatch,
        doi_plan=lambda target, attempt: not (target == VERSION_TARGET and attempt == 1),
    )
    response = _update_license(client)
    assert response.status_code == 502
    assert json.loads(response.get_data(as_text=True))["code"] == "DoiUpdateFailed"
    assert events == [
        ("db", NEW_LICENSE),
        ("doi", CONTAINER_TARGET),
        ("doi", VERSION_TARGET),
        ("db", OLD_LICENSE),
        ("doi", CONTAINER_TARGET),
    ]


def test_nothing_is_resent_when_the_first_record_fails(monkeypatch):
    """Nothing was accepted, so only the database is put back."""
    client, events = _server(monkeypatch, doi_plan=lambda target, attempt: False)
    assert _update_license(client).status_code == 502
    assert events == [
        ("db", NEW_LICENSE),
        ("doi", CONTAINER_TARGET),
        ("db", OLD_LICENSE),
    ]


def test_a_failed_resend_is_reported_as_out_of_step(monkeypatch):
    """The re-send is the last chance to agree; a 502 would claim nothing changed."""
    client, events = _server(
        monkeypatch,
        doi_plan=lambda target, attempt: target == CONTAINER_TARGET and attempt == 1,
    )
    assert _update_license(client).status_code == 500
    assert events[-1] == ("doi", CONTAINER_TARGET)


def test_a_failed_revert_is_reported_as_out_of_step(monkeypatch):
    client, _ = _server(monkeypatch, doi_plan=lambda target, attempt: False, revert_fails=True)
    assert _update_license(client).status_code == 500


def _capture_doi_call(monkeypatch, exported_doi="10.4121/x.v2", raises=None):
    """Capture the identifier the document is built from and the DOI addressed."""
    captured = {}
    monkeypatch.setattr(
        WebServer,
        "_WebServer__metadata_export_parameters",
        lambda self, *a, **k: {"doi": exported_doi},
    )

    def fake_datacite(parameters, **kwargs):
        captured["identifier"] = parameters["doi"]
        return b"<?xml version='1.0'?><resource/>"

    monkeypatch.setattr(wsgi_module.xml_formatter, "datacite", fake_datacite)
    for attribute in ("datacite_url", "datacite_id", "datacite_password", "base_url"):
        monkeypatch.setattr(config, attribute, "x")

    def fake_put(url, **kwargs):
        captured["url"] = url
        if raises is not None:
            raise raises
        return type("_Response", (), {"status_code": 201, "text": ""})()

    monkeypatch.setattr(wsgi_module.requests, "put", fake_put)
    return captured


def test_the_doi_override_also_sets_the_xml_identifier(monkeypatch):
    """The <identifier> comes from the exported parameters, so overriding the
    request target alone would describe the version record as the container."""
    captured = _capture_doi_call(monkeypatch)
    assert WebServer()._WebServer__update_item_doi(
        CONTAINER_UUID, version=None, from_draft=False, doi=CONTAINER_DOI
    )
    assert captured["identifier"] == CONTAINER_DOI
    assert captured["url"].endswith(f"/dois/{CONTAINER_DOI}")


def test_the_exported_identifier_is_kept_without_an_override(monkeypatch):
    captured = _capture_doi_call(monkeypatch)
    assert WebServer()._WebServer__update_item_doi(CONTAINER_UUID, version=2, from_draft=False)
    assert captured["identifier"] == "10.4121/x.v2"
    assert captured["url"].endswith("/dois/10.4121/x.v2")


def test_a_read_timeout_is_reported_as_a_failure(monkeypatch):
    """A read timeout is a Timeout, not a ConnectionError, so it must not escape
    and leave the licence change looking as though it succeeded."""
    _capture_doi_call(monkeypatch, raises=requests.exceptions.ReadTimeout("too slow"))
    assert (
        WebServer()._WebServer__update_item_doi(CONTAINER_UUID, version=2, from_draft=False)
        is False
    )


def test_missing_metadata_is_reported_as_a_failure(monkeypatch):
    """A dataset whose metadata cannot be collected must not be reported sent."""
    monkeypatch.setattr(
        WebServer, "_WebServer__metadata_export_parameters", lambda self, *a, **k: None
    )
    assert (
        WebServer()._WebServer__update_item_doi(CONTAINER_UUID, version=2, from_draft=False)
        is False
    )
