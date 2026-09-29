"""Unit tests for the /v2/account/collections physical sample endpoints."""

from fastapi.testclient import TestClient
from rdflib import URIRef

from djehuty.application import create_app

COLLECTION_UUID = "a1111111-1111-4111-8111-111111111111"
EXISTING_UUID = "b2222222-2222-4222-8222-222222222222"
NEW_UUID = "c3333333-3333-4333-8333-333333333333"
UNKNOWN_UUID = "d4444444-4444-4444-8444-444444444444"
AUTH = {"Authorization": "good"}
BASE = f"/v2/account/collections/{COLLECTION_UUID}/physical_samples"


class _Cache:
    """Records the cache prefixes that were invalidated."""

    def __init__(self):
        self.invalidated = []

    def invalidate_by_prefix(self, prefix):
        self.invalidated.append(prefix)


class _Db:
    """Fake database with just the calls the endpoints make."""

    def __init__(self, drafted=True):
        self.cache = _Cache()
        self.drafted = drafted
        self.draft_created_from = None
        self.sample_calls = []
        self.updated = None
        self.deleted = None
        self.delete_result = True

    def account_by_session_token(self, token):
        return {"uuid": "acct-1", "email": "x"} if token == "good" else None

    def collections(self, **kwargs):
        record = {
            "uuid": "col-1",
            "container_uuid": COLLECTION_UUID,
            "uri": "collection:col-1",
            "title": "Collection",
        }
        if kwargs.get("is_published") is False:
            return [record] if self.drafted else []
        return [] if self.drafted else [record]

    def create_draft_from_published_collection(self, container_uuid):
        self.draft_created_from = container_uuid
        self.drafted = True
        return "draft-uuid"

    def physical_samples(self, **kwargs):
        self.sample_calls.append(kwargs)
        if "collection_uri" in kwargs:
            return [{"container_uuid": EXISTING_UUID, "title": "Existing sample"}]
        if kwargs.get("container_uuid") in (EXISTING_UUID, NEW_UUID):
            return [{"container_uuid": kwargs["container_uuid"]}]
        return []

    def collection_physical_sample_containers(self, collection_uri, limit=None):
        return [{"container_uri": URIRef(f"container:{EXISTING_UUID}")}]

    def update_item_list(self, item_uuid, account_uuid, items, predicate):
        self.updated = (item_uuid, account_uuid, list(items), predicate)
        return True

    def delete_item_from_list(self, subject, predicate, value):
        self.deleted = (subject, predicate, value)
        return self.delete_result


def _client(db=None):
    """Build a test client around DB, or a fresh fake, and return both."""
    db = db or _Db()
    return TestClient(create_app(db)), db


def test_get_lists_the_collection_samples_by_container_uuid():
    """GET returns the collection's published samples by container UUID."""
    client, db = _client()
    response = client.get(BASE, headers=AUTH)
    assert response.status_code == 200
    assert response.json() == [{"uuid": EXISTING_UUID, "title": "Existing sample"}]
    listing = db.sample_calls[-1]
    assert listing["collection_uri"] == "collection:col-1"
    assert listing["is_latest"] is True
    assert listing["is_published"] is True


def test_post_appends_to_the_existing_samples():
    """POST keeps the existing samples and adds the new ones."""
    client, db = _client()
    response = client.post(BASE, json={"samples": [NEW_UUID]}, headers=AUTH)
    assert response.status_code == 205
    item_uuid, account_uuid, items, predicate = db.updated
    assert item_uuid == "col-1"
    assert account_uuid == "acct-1"
    assert items == [URIRef(f"container:{EXISTING_UUID}"), URIRef(f"container:{NEW_UUID}")]
    assert predicate == "physical_samples"
    assert "physical-samples" in db.cache.invalidated


def test_put_replaces_the_samples():
    """PUT replaces the list with the given samples."""
    client, db = _client()
    response = client.put(BASE, json={"samples": [NEW_UUID]}, headers=AUTH)
    assert response.status_code == 205
    assert db.updated[2] == [URIRef(f"container:{NEW_UUID}")]


def test_a_sample_listed_twice_is_stored_once():
    """A repeated sample is stored once."""
    client, db = _client()
    response = client.put(BASE, json={"samples": [NEW_UUID, NEW_UUID]}, headers=AUTH)
    assert response.status_code == 205
    assert db.updated[2] == [URIRef(f"container:{NEW_UUID}")]


def test_put_with_an_empty_list_clears_the_samples():
    """PUT with an empty list empties the collection's samples."""
    client, db = _client()
    response = client.put(BASE, json={"samples": []}, headers=AUTH)
    assert response.status_code == 205
    assert db.updated[2] == []


def test_missing_samples_field_is_a_400():
    """A body without 'samples' is a 400 with code NoSamplesField."""
    client, db = _client()
    response = client.post(BASE, json={}, headers=AUTH)
    assert response.status_code == 400
    assert response.json()["code"] == "NoSamplesField"
    assert db.updated is None


def test_an_invalid_uuid_is_a_400():
    """A value that is not a UUID is rejected before anything is written."""
    client, db = _client()
    response = client.post(BASE, json={"samples": ["short"]}, headers=AUTH)
    assert response.status_code == 400
    assert db.updated is None


def test_an_unknown_or_unpublished_sample_is_a_500():
    """An unknown or unpublished sample is a 500, as in the legacy handler."""
    client, db = _client()
    response = client.post(BASE, json={"samples": [UNKNOWN_UUID]}, headers=AUTH)
    assert response.status_code == 500
    assert db.updated is None


def test_a_published_collection_is_drafted_before_it_is_changed():
    """Changing a published collection drafts it first."""
    client, db = _client(_Db(drafted=False))
    response = client.post(BASE, json={"samples": [NEW_UUID]}, headers=AUTH)
    assert response.status_code == 205
    assert db.draft_created_from == COLLECTION_UUID
    assert db.updated is not None


def test_an_unknown_collection_is_a_404():
    """Every method answers 404 for a collection the account does not have."""
    db = _Db()
    db.collections = lambda **kwargs: []
    client, _ = _client(db)
    assert client.get(BASE, headers=AUTH).status_code == 404
    assert client.post(BASE, json={"samples": []}, headers=AUTH).status_code == 404
    assert client.delete(f"{BASE}/{NEW_UUID}", headers=AUTH).status_code == 404


def test_delete_removes_the_sample_by_container_uri():
    """DELETE removes the sample by its container URI."""
    client, db = _client()
    response = client.delete(f"{BASE}/{NEW_UUID}", headers=AUTH)
    assert response.status_code == 204
    assert db.deleted == ("collection:col-1", "physical_samples", URIRef(f"container:{NEW_UUID}"))
    assert "physical-samples" in db.cache.invalidated


def test_delete_of_an_unknown_sample_is_a_404():
    """DELETE of an unknown sample is a 404 and removes nothing."""
    client, db = _client()
    response = client.delete(f"{BASE}/{UNKNOWN_UUID}", headers=AUTH)
    assert response.status_code == 404
    assert db.deleted is None


def test_a_failed_delete_is_forbidden():
    """A removal the database refuses is a 403."""
    db = _Db()
    db.delete_result = False
    client, _ = _client(db)
    assert client.delete(f"{BASE}/{NEW_UUID}", headers=AUTH).status_code == 403


def test_every_method_requires_a_session():
    """Every method refuses a request without a session."""
    client, db = _client()
    assert client.get(BASE).status_code in (401, 403)
    assert client.post(BASE, json={"samples": []}).status_code in (401, 403)
    assert client.put(BASE, json={"samples": []}).status_code in (401, 403)
    assert client.delete(f"{BASE}/{NEW_UUID}").status_code in (401, 403)
    assert db.updated is None
