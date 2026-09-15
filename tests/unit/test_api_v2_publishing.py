"""Unit tests for the /v2 publishing, DOI and file-registration endpoints.

Pins the batch-2 ports from the side-effect catalog: DOI reservation goes
through the DataCite service, publish assigns the review and sends the
notification e-mails, and POST on the files collection registers uploads.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app
from djehuty.services import datacite

DATASET_UUID = "a" * 36
COLLECTION_UUID = "b" * 36
AUTH = {"Authorization": "good"}


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _Db:
    def __init__(self):
        self.cache = _Cache()
        self.review_update = None
        self.published = None
        self.collection_update = None
        self.inserted_file = None

    def account_by_session_token(self, token):
        if token in ("good", "reviewer-token"):
            return {"uuid": "acct-1", "email": "owner@example.org"}
        return None

    def account_by_uuid(self, uuid):
        return {"uuid": uuid, "email": "owner@example.org"}

    def datasets(self, **kwargs):
        record = {
            "uuid": "ds-1",
            "container_uuid": DATASET_UUID,
            "uri": "dataset:ds-1",
            "review_uri": "review:rev-1",
            "account_uuid": "acct-1",
            "title": "Publish me",
            "container_doi": "10.5074/x",
        }
        if kwargs.get("container_uuid") == DATASET_UUID or kwargs.get("dataset_uuid") == "ds-1":
            return [record]
        return []

    def collections(self, **kwargs):
        if kwargs.get("container_uuid") == COLLECTION_UUID:
            return [{"uuid": "col-1", "container_uuid": COLLECTION_UUID, "uri": "collection:col-1"}]
        return []

    def may_review(self, token):
        return token == "good"

    def may_review_institution(self, token):
        return False

    def update_review(self, review_uri, **kwargs):
        self.review_update = (review_uri, kwargs)
        return True

    def container(self, *a, **k):
        return {"latest_published_version_number": 1}

    def publish_dataset(self, container_uuid, account_uuid):
        self.published = (container_uuid, account_uuid)
        return True

    def update_collection(self, collection_uuid, account_uuid, **kwargs):
        self.collection_update = (collection_uuid, account_uuid, kwargs)
        return True

    def insert_file(self, **kwargs):
        self.inserted_file = kwargs
        return "file-1"

    def reviewer_email_addresses(self):
        return ["reviewer@example.org"]

    def institutional_reviewer_email_addresses(self, domain):
        return []

    def may_receive_email_notifications(self, address):
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client(db=None):
    db = db or _Db()
    return TestClient(create_app(db)), db


def test_reserve_dataset_doi_uses_the_datacite_service(monkeypatch):
    calls = {}

    def fake_reserve(db, account_uuid, item, version=None, item_type="dataset"):
        calls["args"] = (account_uuid, item["uuid"], version, item_type)
        return "10.5074/reserved"

    monkeypatch.setattr(datacite, "reserve_and_save_doi", fake_reserve)
    client, db = _client()
    response = client.post(f"/v2/account/articles/{DATASET_UUID}/reserve_doi", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"doi": "10.5074/reserved"}
    assert calls["args"] == ("acct-1", "ds-1", None, "dataset")


def test_reserve_collection_doi_saves_the_reserved_doi(monkeypatch):
    monkeypatch.setattr(
        datacite, "datacite_reserve_doi", lambda doi=None: {"data": {"id": "10.5074/coll"}}
    )
    client, db = _client()
    response = client.post(f"/v2/account/collections/{COLLECTION_UUID}/reserve_doi", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"doi": "10.5074/coll"}
    collection_uuid, account_uuid, kwargs = db.collection_update
    assert collection_uuid == "col-1"
    assert kwargs == {"doi": "10.5074/coll"}


def test_publish_assigns_the_review_and_notifies(monkeypatch):
    from djehuty.services import notifications

    sent = []
    monkeypatch.setattr(
        notifications,
        "send_templated_email",
        lambda db, email, addresses, subject, template, **ctx: sent.append((template, addresses)),
    )
    monkeypatch.setattr(
        notifications,
        "send_email_to_reviewers",
        lambda db, email, subject, template, **ctx: sent.append((template, "reviewers")),
    )
    client, db = _client()
    client.cookies.set("impersonator_djehuty_session", "good")
    response = client.post(f"/v2/account/articles/{DATASET_UUID}/publish", headers=AUTH)
    assert response.status_code == 201
    assert response.json()["location"].endswith(f"/review/published/{DATASET_UUID}")
    assert db.published == (DATASET_UUID, "acct-1")
    review_uri, kwargs = db.review_update
    assert review_uri == "review:rev-1"
    assert kwargs["status"] == "assigned"
    assert ("dataset_approved", ["owner@example.org"]) in sent
    assert ("published_dataset_notification", "reviewers") in sent


def test_publish_requires_reviewer_permissions():
    class _NoReviewDb(_Db):
        def may_review(self, token):
            return False

    client, db = _client(_NoReviewDb())
    response = client.post(f"/v2/account/articles/{DATASET_UUID}/publish", headers=AUTH)
    assert response.status_code == 403
    assert db.published is None


def test_post_files_registers_an_upload():
    client, db = _client()
    response = client.post(
        f"/v2/account/articles/{DATASET_UUID}/files",
        json={"name": "data.csv", "size": 1234, "md5": "d" * 32},
        headers=AUTH,
    )
    assert response.status_code == 201
    assert response.json()["location"].endswith(f"/articles/{DATASET_UUID}/files/file-1")
    kwargs = db.inserted_file
    assert kwargs["name"] == "data.csv"
    assert kwargs["size"] == 1234
    assert kwargs["is_link_only"] is False
    assert kwargs["upload_token"] == "good"


def test_post_files_registers_a_link():
    client, db = _client()
    response = client.post(
        f"/v2/account/articles/{DATASET_UUID}/files",
        json={"link": "https://example.org/data"},
        headers=AUTH,
    )
    assert response.status_code == 201
    kwargs = db.inserted_file
    assert kwargs["is_link_only"] is True
    assert kwargs["download_url"] == "https://example.org/data"
