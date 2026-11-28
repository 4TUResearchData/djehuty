"""Publish endpoints reserve the DOI for the version they publish."""

import logging

import pytest
from fastapi.testclient import TestClient
from werkzeug.test import Client

from djehuty.application import create_app
from djehuty.services import datacite, notifications
from djehuty.utils import convenience
from djehuty.web.config import config
from djehuty.web.wsgi import WebServer

convenience.add_logging_level("ACCESS", logging.INFO + 5)
convenience.add_logging_level("AUDIT", logging.INFO + 6)

CONTAINER_UUID = "c" * 8 + "-cccc-4ccc-8ccc-" + "c" * 12
NEXT_VERSION = 4

DATASET = {
    "uuid": "d" * 8 + "-dddd-4ddd-8ddd-" + "d" * 12,
    "uri": "dataset:d",
    "container_uuid": CONTAINER_UUID,
    "account_uuid": "a1",
    "review_uri": "review:r",
    "title": "Publish me",
    "container_doi": "10.5074/x",
}

COLLECTION = {
    "uuid": "e" * 8 + "-eeee-4eee-8eee-" + "e" * 12,
    "uri": "collection:e",
    "container_uuid": CONTAINER_UUID,
    "title": "Publish me",
    "description": "A collection.",
    "group_id": 1,
    "publisher": "4TU.ResearchData",
    "language": "en",
}


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _Db:
    def __init__(self):
        self.cache = _Cache()
        self.published = None

    def account_by_session_token(self, token):
        return {"uuid": "a1", "email": "o@4tu.nl", "group_id": 1} if token == "good" else None

    def account_by_uuid(self, uuid):
        return {"uuid": uuid, "email": "o@4tu.nl"}

    def may_review(self, token):
        return token == "good"

    def may_review_institution(self, token):
        return False

    def update_review(self, *args, **kwargs):
        return True

    def container(self, *args, **kwargs):
        return {"latest_published_version_number": 1}

    def highest_version(self, container_uuid):
        return NEXT_VERSION - 1

    def datasets(self, **kwargs):
        return [dict(DATASET)]

    def collections(self, **kwargs):
        return [dict(COLLECTION)]

    def authors(self, **kwargs):
        return [{"uuid": "author"}]

    def tags(self, **kwargs):
        return [{"tag": "tag"}]

    def categories(self, **kwargs):
        return [{"uuid": "category"}]

    def publish_dataset(self, container_uuid, account_uuid, version):
        self.published = version
        return True

    def publish_collection(self, container_uuid, account_uuid, version):
        self.published = version
        return True

    def __getattr__(self, name):
        return lambda *args, **kwargs: []


@pytest.fixture
def doi_versions(monkeypatch):
    """Record the version of every DOI reservation and update, on both stacks."""
    reserved, updated = [], []
    monkeypatch.setattr(config, "in_production", True)
    monkeypatch.setattr(config, "in_preproduction", False)
    monkeypatch.setattr(
        datacite,
        "reserve_and_save_doi",
        lambda db, account_uuid, item, version=None, item_type="dataset": (
            reserved.append(version) or "10.5074/x"
        ),
    )
    monkeypatch.setattr(
        datacite,
        "update_item_doi",
        lambda db, item_id, version=None, item_type="dataset", from_draft=True: (
            updated.append(version) or True
        ),
    )
    monkeypatch.setattr(
        WebServer,
        "_WebServer__reserve_and_save_doi",
        lambda self, account_uuid, item, version=None, item_type="dataset": (
            reserved.append(version) or "10.5074/x"
        ),
    )
    monkeypatch.setattr(
        WebServer,
        "_WebServer__update_item_doi",
        lambda self, item_id, version=None, item_type="dataset", **kwargs: (
            updated.append(version) or True
        ),
    )
    return reserved, updated


@pytest.fixture
def legacy(monkeypatch):
    monkeypatch.setattr(
        WebServer, "_WebServer__dataset_by_id_or_uri", lambda self, *a, **k: dict(DATASET)
    )
    monkeypatch.setattr(
        WebServer, "_WebServer__collection_by_id_or_uri", lambda self, *a, **k: dict(COLLECTION)
    )
    monkeypatch.setattr(
        WebServer, "_WebServer__git_repository_url_for_dataset", lambda self, dataset: None
    )
    monkeypatch.setattr(WebServer, "_WebServer__send_templated_email", lambda *a, **k: None)
    monkeypatch.setattr(WebServer, "_WebServer__send_email_to_reviewers", lambda *a, **k: None)
    db = _Db()
    server = WebServer()
    server.db = db
    client = Client(server)
    client.set_cookie("djehuty_session", "good", domain="localhost")
    client.set_cookie("impersonator_djehuty_session", "good", domain="localhost")
    return client, db


@pytest.mark.parametrize(
    "path",
    [
        "/v2/account/articles/{}/publish",
        "/v3/datasets/{}/publish",
        "/v3/collections/{}/publish",
    ],
)
def test_publish_reserves_the_version_it_publishes(doi_versions, monkeypatch, path):
    reserved, updated = doi_versions
    monkeypatch.setattr(notifications, "send_templated_email", lambda *a, **k: None)
    monkeypatch.setattr(notifications, "send_email_to_reviewers", lambda *a, **k: None)
    db = _Db()
    client = TestClient(create_app(db))
    client.cookies.set("djehuty_session", "good")
    client.cookies.set("impersonator_djehuty_session", "good")
    response = client.post(path.format(CONTAINER_UUID), headers={"Authorization": "good"})
    assert response.status_code == 201
    assert reserved == updated == [None, NEXT_VERSION]
    assert db.published == NEXT_VERSION


@pytest.mark.parametrize("item_type", ["datasets", "collections"])
def test_legacy_publish_reserves_the_version_it_publishes(doi_versions, legacy, item_type):
    reserved, updated = doi_versions
    client, db = legacy
    response = client.post(
        f"/v3/{item_type}/{CONTAINER_UUID}/publish",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    assert response.status_code == 201
    assert reserved == updated == [None, NEXT_VERSION]
    assert db.published == NEXT_VERSION
