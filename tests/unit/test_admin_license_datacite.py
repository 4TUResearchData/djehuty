"""Unit tests for /admin/update-published-dataset/license/update.

A published dataset has two DataCite records: the container DOI, which always
points to the newest version, and the version DOI. When an administrator
changes the licence, both records are updated. If DataCite refuses one, the
change is undone in the database and in any record DataCite already accepted.

The database and the DataCite call are replaced by fakes that append each call
to EVENTS, so a test can check what was written and in which order.
"""

import json
import logging
import os

import requests
from jinja2 import Environment, FileSystemLoader
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

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "src",
    "djehuty",
    "web",
    "resources",
    "sparql_templates",
)


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _Db:
    """Records the licence writes it is asked to make, in order."""

    def __init__(self, events, previous_license=OLD_LICENSE):
        self.cache = _Cache()
        self.events = events
        self.previous_license = previous_license
        self.revert_fails = False

    def may_administer(self, token, account=None):
        return token == "admin-token"

    def account_by_session_token(self, token):
        return {"uuid": "admin-1"}

    def licenses(self):
        return [{"url": OLD_LICENSE}, {"url": NEW_LICENSE}]

    def datasets(self, **kwargs):
        if kwargs.get("is_latest") and kwargs.get("dataset_uuid") == DATASET_UUID:
            record = {
                "uuid": DATASET_UUID,
                "version": 2,
                "container_doi": CONTAINER_DOI,
                "account_uuid": "owner-1",
            }
            if self.previous_license is not None:
                record["license_url"] = self.previous_license
            return [record]
        return []

    def admin_update_license(self, container_uuid, dataset_uuid, url, admin_uuid, **kwargs):
        if self.revert_fails and any(event[0] == "db" for event in self.events):
            return False
        self.events.append(("db", url))
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _server(
    monkeypatch,
    in_production=True,
    doi_plan=None,
    revert_fails=False,
    previous_license=OLD_LICENSE,
):
    """Build a client whose DOI sends are recorded instead of performed.

    DOI_PLAN(target, attempt) decides whether DataCite accepts a send; the
    attempt counter separates a first send from a re-send of the same record.
    """
    events = []
    server = WebServer()
    server.db = _Db(events, previous_license=previous_license)
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
    """Both records are updated, the container record first because the
    approval email cites it."""
    client, events = _server(monkeypatch)
    assert _update_license(client).status_code == 204
    assert events == [
        ("db", NEW_LICENSE),
        ("doi", CONTAINER_TARGET),
        ("doi", VERSION_TARGET),
    ]


def test_datacite_is_untouched_outside_production(monkeypatch):
    """Outside production only the database is changed. DataCite is not called."""
    client, events = _server(monkeypatch, in_production=False)
    assert _update_license(client).status_code == 204
    assert events == [("db", NEW_LICENSE)]


def test_accepted_record_is_resent_after_the_revert(monkeypatch):
    """DataCite accepts the container record and refuses the version record.

    The database goes back to the old licence, and the container record is sent
    again so DataCite shows the old licence."""
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
    """DataCite refuses the container record, so no record was changed.

    The database is written back to the old licence, and nothing is sent again.
    """
    client, events = _server(monkeypatch, doi_plan=lambda target, attempt: False)
    assert _update_license(client).status_code == 502
    assert events == [
        ("db", NEW_LICENSE),
        ("doi", CONTAINER_TARGET),
        ("db", OLD_LICENSE),
    ]


def test_a_dataset_without_a_licence_is_cleared_again(monkeypatch):
    """The dataset had no licence, and DataCite refuses the version record.

    The revert passes None to the database, which removes the new licence
    instead of keeping it, and the container record is sent again without one.
    """
    client, events = _server(
        monkeypatch,
        previous_license=None,
        doi_plan=lambda target, attempt: not (target == VERSION_TARGET and attempt == 1),
    )
    response = _update_license(client)
    assert response.status_code == 502
    assert json.loads(response.get_data(as_text=True))["code"] == "DoiUpdateFailed"
    assert events == [
        ("db", NEW_LICENSE),
        ("doi", CONTAINER_TARGET),
        ("doi", VERSION_TARGET),
        ("db", None),
        ("doi", CONTAINER_TARGET),
    ]


def _render_update_license(new_license_url):
    environment = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    return environment.get_template("admin_update_license.sparql").render(
        {
            "state_graph": "djehuty://test",
            "container_uri": f"container:{CONTAINER_UUID}",
            "dataset_uri": f"dataset:{DATASET_UUID}",
            "new_license_url": new_license_url,
        }
    )


def test_clearing_the_licence_inserts_nothing():
    """With None, the query only deletes the licence. It must not insert the
    text "None" as a licence."""
    query = _render_update_license(None)
    assert "?dataset djht:license ?current_license" in query
    assert "INSERT" not in query
    assert "None" not in query


def test_setting_a_licence_replaces_the_old_one():
    """With a URL, the query deletes the old licence and inserts the new one."""
    query = _render_update_license(NEW_LICENSE)
    assert "?dataset djht:license ?current_license" in query
    assert f"?dataset djht:license <{NEW_LICENSE}>" in query


def test_a_failed_resend_is_reported_as_out_of_step(monkeypatch):
    """DataCite accepts the container record, refuses the version record, then
    refuses the container record when it is sent again.

    DataCite keeps the new licence while the database is back on the old one,
    so the response is a 500. A 502 would tell the admin nothing was changed."""
    client, events = _server(
        monkeypatch,
        doi_plan=lambda target, attempt: target == CONTAINER_TARGET and attempt == 1,
    )
    assert _update_license(client).status_code == 500
    assert events == [
        ("db", NEW_LICENSE),
        ("doi", CONTAINER_TARGET),
        ("doi", VERSION_TARGET),
        ("db", OLD_LICENSE),
        ("doi", CONTAINER_TARGET),
    ]


def test_a_failed_revert_is_reported_as_out_of_step(monkeypatch):
    """DataCite refuses the container record and the database revert fails.

    The database keeps the new licence while DataCite has the old one, so the
    response is a 500."""
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
    """Sending the container record puts the container DOI in both the URL and
    the XML <identifier>. Otherwise the container record would be sent XML
    that names the version DOI."""
    captured = _capture_doi_call(monkeypatch)
    assert WebServer()._WebServer__update_item_doi(
        CONTAINER_UUID, version=None, from_draft=False, doi=CONTAINER_DOI
    )
    assert captured["identifier"] == CONTAINER_DOI
    assert captured["url"].endswith(f"/dois/{CONTAINER_DOI}")


def test_the_exported_identifier_is_kept_without_an_override(monkeypatch):
    """Without a DOI override, the version DOI is used in both the URL and the XML."""
    captured = _capture_doi_call(monkeypatch)
    assert WebServer()._WebServer__update_item_doi(CONTAINER_UUID, version=2, from_draft=False)
    assert captured["identifier"] == "10.4121/x.v2"
    assert captured["url"].endswith("/dois/10.4121/x.v2")


def test_a_read_timeout_is_reported_as_a_failure(monkeypatch):
    """A DataCite read timeout counts as a failed send, so the licence change
    is undone instead of the request crashing with the new licence kept."""
    _capture_doi_call(monkeypatch, raises=requests.exceptions.ReadTimeout("too slow"))
    assert (
        WebServer()._WebServer__update_item_doi(CONTAINER_UUID, version=2, from_draft=False)
        is False
    )


def test_missing_metadata_is_reported_as_a_failure(monkeypatch):
    """If the dataset's metadata cannot be collected, the send counts as failed."""
    monkeypatch.setattr(
        WebServer, "_WebServer__metadata_export_parameters", lambda self, *a, **k: None
    )
    assert (
        WebServer()._WebServer__update_item_doi(CONTAINER_UUID, version=2, from_draft=False)
        is False
    )
