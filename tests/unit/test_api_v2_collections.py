"""Unit tests for the /v2/account/collections endpoints (djehuty.api.v2).

Pins the AS-IS behaviours the e2e contract suite caught missing: draft
collections appear in the private listing, POST appends articles while PUT
replaces them, and removing an article resolves the dataset's container URI.
"""

from fastapi.testclient import TestClient
from rdflib import URIRef

from djehuty.application import create_app

DRAFT_UUID = "a" * 36
EXISTING_UUID = "b" * 36
NEW_UUID = "c" * 36
CATEGORY_UUID = "d" * 36
AUTH = {"Authorization": "good"}


class _Cache:
    def __init__(self):
        self.invalidated = []

    def invalidate_by_prefix(self, prefix):
        self.invalidated.append(prefix)


class _Db:
    def __init__(self):
        self.cache = _Cache()
        self.collection_calls = []
        self.author_calls = []
        self.funding_calls = []
        self.category_calls = []
        self.updated = None
        self.deleted = None

    def account_by_session_token(self, token):
        return {"uuid": "acct-1", "email": "x"} if token == "good" else None

    def collections(self, **kwargs):
        self.collection_calls.append(kwargs)
        if kwargs.get("is_published") is False:
            return [
                {
                    "uuid": "col-1",
                    "container_uuid": DRAFT_UUID,
                    "uri": "collection:col-1",
                    "title": "Draft collection",
                }
            ]
        if kwargs.get("is_published") is None:
            return [{"container_uuid": DRAFT_UUID, "title": "Draft collection"}]
        return []

    def datasets(self, **kwargs):
        if "collection_uri" in kwargs:
            return [{"container_uuid": EXISTING_UUID}]
        if "container_uuid" in kwargs:
            return [{"container_uri": f"container:{kwargs['container_uuid']}"}]
        return []

    def authors(self, **kwargs):
        self.author_calls.append(kwargs)
        return []

    def categories(self, **kwargs):
        self.category_calls.append(kwargs)
        return []

    def category_by_id(self, **kwargs):
        return {"uuid": CATEGORY_UUID}

    def fundings(self, **kwargs):
        self.funding_calls.append(kwargs)
        return []

    def update_item_list(self, item_uuid, account_uuid, items, predicate):
        self.updated = (item_uuid, account_uuid, list(items), predicate)
        return True

    def insert_collection(self, **kwargs):
        self.insert_collection_kwargs = kwargs
        return ("new-container-uuid", "new-collection-uuid")

    def delete_item_from_list(self, subject, predicate, value):
        self.deleted = (subject, predicate, value)
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client(db=None):
    db = db or _Db()
    return TestClient(create_app(db)), db


def test_private_listing_includes_draft_collections():
    client, db = _client()
    response = client.get("/v2/account/collections", headers=AUTH)
    assert response.status_code == 200
    assert [record["uuid"] for record in response.json()] == [DRAFT_UUID]
    listing = db.collection_calls[-1]
    assert listing["is_published"] is None
    assert listing["is_latest"] is None


def test_post_appends_articles_to_the_existing_list():
    client, db = _client()
    response = client.post(
        f"/v2/account/collections/{DRAFT_UUID}/articles",
        json={"articles": [NEW_UUID]},
        headers=AUTH,
    )
    assert response.status_code == 205
    item_uuid, account_uuid, items, predicate = db.updated
    assert item_uuid == "col-1"
    assert account_uuid == "acct-1"
    assert items == [URIRef(f"container:{EXISTING_UUID}"), URIRef(f"container:{NEW_UUID}")]
    assert predicate == "datasets"
    assert "datasets" in db.cache.invalidated


def test_put_replaces_the_article_list():
    client, db = _client()
    response = client.put(
        f"/v2/account/collections/{DRAFT_UUID}/articles",
        json={"articles": [NEW_UUID]},
        headers=AUTH,
    )
    assert response.status_code == 205
    assert db.updated[2] == [URIRef(f"container:{NEW_UUID}")]


def test_post_without_articles_field_is_a_400():
    client, db = _client()
    response = client.post(
        f"/v2/account/collections/{DRAFT_UUID}/articles", json={}, headers=AUTH
    )
    assert response.status_code == 400
    assert response.json()["code"] == "NoArticlesField"
    assert db.updated is None


def test_delete_removes_the_dataset_by_container_uri():
    client, db = _client()
    response = client.delete(
        f"/v2/account/collections/{DRAFT_UUID}/articles/{NEW_UUID}", headers=AUTH
    )
    assert response.status_code == 204
    assert db.deleted == ("collection:col-1", "datasets", f"container:{NEW_UUID}")
    assert "datasets" in db.cache.invalidated


def test_ui_limit_10000_is_accepted():
    client, db = _client()
    response = client.get(
        f"/v2/account/collections/{DRAFT_UUID}/articles",
        params={"limit": 10000, "order": "id", "order_direction": "asc"},
        headers=AUTH,
    )
    assert response.status_code == 200


def test_absent_paging_stays_unbounded():
    client, db = _client()
    client.get("/v2/account/collections", headers=AUTH)
    listing = db.collection_calls[-1]
    assert listing["limit"] is None
    assert listing["offset"] is None


def test_mixing_page_and_limit_is_a_400():
    client, db = _client()
    response = client.get(
        "/v2/account/collections", params={"page": 1, "limit": 5}, headers=AUTH
    )
    assert response.status_code == 400
    assert response.json()["code"] == "InvalidPagingOptions"
    assert db.collection_calls == []


def test_post_categories_adds_to_the_collection():
    client, db = _client()
    response = client.post(
        f"/v2/account/collections/{DRAFT_UUID}/categories",
        json={"categories": ["13431"]},
        headers=AUTH,
    )
    assert response.status_code == 205
    item_uuid, account_uuid, uris, predicate = db.updated
    assert item_uuid == "col-1"
    assert predicate == "categories"
    assert len(uris) == 1 and CATEGORY_UUID in str(uris[0])
    listing = db.category_calls[-1]
    assert listing["is_published"] is False
    assert listing["account_uuid"] == "acct-1"


def test_post_categories_without_parameter_is_a_400():
    client, db = _client()
    response = client.post(
        f"/v2/account/collections/{DRAFT_UUID}/categories", json={}, headers=AUTH
    )
    assert response.status_code == 400
    assert response.json()["code"] == "MissingRequiredField"
    assert db.updated is None


def test_draft_collection_authors_and_funding_are_visible():
    client, db = _client()
    assert client.get(
        f"/v2/account/collections/{DRAFT_UUID}/authors", headers=AUTH
    ).status_code == 200
    assert client.get(
        f"/v2/account/collections/{DRAFT_UUID}/funding", headers=AUTH
    ).status_code == 200
    assert db.author_calls[-1]["is_published"] is False
    assert db.funding_calls[-1]["is_published"] is False
    assert db.funding_calls[-1]["account_uuid"] == "acct-1"


class _MembersDb(_Db):
    def authors(self, **kwargs):
        self.author_calls.append(kwargs)
        return [{"uuid": "au-1", "id": 1}, {"uuid": "au-2", "id": 2}]

    def fundings(self, **kwargs):
        self.funding_calls.append(kwargs)
        return [{"uuid": "fu-1"}, {"uuid": "fu-2"}]


def test_delete_collection_author_rewrites_the_author_list():
    client, db = _client(_MembersDb())
    response = client.delete(
        f"/v2/account/collections/{DRAFT_UUID}/authors/au-1", headers=AUTH
    )
    assert response.status_code == 204
    item_uuid, account_uuid, uris, predicate = db.updated
    assert item_uuid == "col-1"
    assert predicate == "authors"
    assert len(uris) == 1 and "au-2" in str(uris[0])
    assert db.author_calls[-1]["is_published"] is False


def test_delete_collection_funding_rewrites_the_funding_list():
    client, db = _client(_MembersDb())
    response = client.delete(
        f"/v2/account/collections/{DRAFT_UUID}/funding/fu-1", headers=AUTH
    )
    assert response.status_code == 204
    item_uuid, account_uuid, uris, predicate = db.updated
    assert predicate == "funding_list"
    assert len(uris) == 1 and "fu-2" in str(uris[0])


def test_delete_collection_funding_without_any_funding_is_a_404():
    client, db = _client()
    response = client.delete(
        f"/v2/account/collections/{DRAFT_UUID}/funding/fu-1", headers=AUTH
    )
    assert response.status_code == 404
    assert db.updated is None


def test_delete_collection_category_removes_by_category_uri():
    client, db = _client()
    response = client.delete(
        f"/v2/account/collections/{DRAFT_UUID}/categories/13431", headers=AUTH
    )
    assert response.status_code == 204
    subject, predicate, value = db.deleted
    assert subject == "collection:col-1"
    assert predicate == "categories"
    assert CATEGORY_UUID in str(value)


def test_create_collection_persists_the_list_fields():
    client, db = _client()
    response = client.post(
        "/v2/account/collections",
        json={
            "title": "Full collection",
            "articles": [NEW_UUID],
            "authors": [{"first_name": "A", "last_name": "B"}],
            "tags": ["kw-1"],
            "references": ["https://example.org"],
        },
        headers=AUTH,
    )
    assert response.status_code == 200
    kwargs = db.insert_collection_kwargs
    assert kwargs["datasets"] == [NEW_UUID]
    assert kwargs["authors"] == [{"first_name": "A", "last_name": "B"}]
    assert kwargs["tags"] == ["kw-1"]
    assert kwargs["references"] == ["https://example.org"]


class _NoDatasetsDb(_Db):
    def datasets(self, **kwargs):
        return []


def test_delete_unknown_dataset_is_a_404():
    client, db = _client(_NoDatasetsDb())
    response = client.delete(
        f"/v2/account/collections/{DRAFT_UUID}/articles/{NEW_UUID}", headers=AUTH
    )
    assert response.status_code == 404
    assert db.deleted is None
