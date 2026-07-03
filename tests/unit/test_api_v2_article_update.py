"""Unit tests for the /v2/account/articles update and file-removal endpoints.

Pins the AS-IS behaviours the e2e suite caught missing: the PUT persists the
fields the web UI sends (defined_type, categories, agreements, git fields) and
DELETE on the files collection honours the remove_all body.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app

DATASET_UUID = "a" * 36
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
        self.update_kwargs = None
        self.deleted_all = None

    def account_by_session_token(self, token):
        return {"uuid": "acct-1", "email": "x"} if token == "good" else None

    def datasets(self, **kwargs):
        if kwargs.get("container_uuid") == DATASET_UUID:
            return [
                {
                    "uuid": "ds-1",
                    "container_uuid": DATASET_UUID,
                    "uri": "dataset:ds-1",
                    "review_uri": "review:rev-1",
                    "account_uuid": "acct-1",
                }
            ]
        return []

    def category_by_id(self, **kwargs):
        return {"uuid": CATEGORY_UUID}

    def license_url_by_id(self, license_id):
        return None

    def update_dataset(self, dataset_uuid, account_uuid, **kwargs):
        self.update_kwargs = {"dataset_uuid": dataset_uuid, "account_uuid": account_uuid, **kwargs}
        return True

    def is_depositor(self, token, account):
        return True

    def insert_dataset(self, **kwargs):
        self.insert_kwargs = kwargs
        return ("new-container-uuid", "new-dataset-uuid")

    def delete_items_all_from_list(self, subject, predicate):
        self.deleted_all = (subject, predicate)
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client():
    db = _Db()
    return TestClient(create_app(db)), db


def test_update_persists_the_fields_the_ui_sends():
    client, db = _client()
    response = client.put(
        f"/v2/account/articles/{DATASET_UUID}",
        json={
            "title": "Software deposit",
            "defined_type": "software",
            "categories": ["13431"],
            "tags": ["e2e"],
            "references": ["https://example.org"],
            "git_repository_name": "my-repo",
            "git_code_hosting_url": "https://git.example.org/my-repo",
            "agreed_to_deposit_agreement": True,
            "agreed_to_publish": True,
        },
        headers=AUTH,
    )
    assert response.status_code == 205
    kwargs = db.update_kwargs
    assert kwargs["defined_type_name"] == "software"
    assert kwargs["defined_type"] == 9
    assert kwargs["categories"] == [{"uuid": CATEGORY_UUID}]
    assert kwargs["tags"] == [{"tag": "e2e"}]
    assert kwargs["references"] == [{"url": "https://example.org"}]
    assert kwargs["git_repository_name"] == "my-repo"
    assert kwargs["git_code_hosting_url"] == "https://git.example.org/my-repo"
    assert kwargs["agreed_to_deposit_agreement"] is True
    assert kwargs["agreed_to_publish"] is True


def test_update_accepts_keywords_as_tags_alias():
    client, db = _client()
    response = client.put(
        f"/v2/account/articles/{DATASET_UUID}",
        json={"title": "Keywords alias", "keywords": ["kw-1"]},
        headers=AUTH,
    )
    assert response.status_code == 205
    assert db.update_kwargs["tags"] == [{"tag": "kw-1"}]


class _ReviewDb(_Db):
    def __init__(self):
        super().__init__()
        self.review_update = None
        self.seen_by_reviewer = None

    def may_review(self, token):
        return token == "reviewer-token"

    def account_by_session_token(self, token):
        if token == "reviewer-token":
            return {"uuid": "reviewer-1", "email": "r"}
        return super().account_by_session_token(token)

    def reviews(self, **kwargs):
        return [{"uuid": "rev-1"}]

    def update_review(self, review_uri, **kwargs):
        self.review_update = (review_uri, kwargs)
        return True

    def dataset_update_seen_by_reviewer(self, dataset_uuid):
        self.seen_by_reviewer = dataset_uuid


def test_reviewer_save_assigns_the_review():
    db = _ReviewDb()
    client = TestClient(create_app(db))
    client.cookies.set("impersonator_djehuty_session", "reviewer-token")
    response = client.put(
        f"/v2/account/articles/{DATASET_UUID}",
        json={"title": "Reviewed save"},
        headers=AUTH,
    )
    assert response.status_code == 205
    review_uri, kwargs = db.review_update
    assert review_uri == "review:rev-1"
    assert kwargs["status"] == "assigned"
    assert kwargs["assigned_to"] == "reviewer-1"
    assert kwargs["author_account_uuid"] == "acct-1"
    assert db.seen_by_reviewer == "ds-1"


def test_depositor_save_does_not_touch_the_review():
    db = _ReviewDb()
    client = TestClient(create_app(db))
    response = client.put(
        f"/v2/account/articles/{DATASET_UUID}",
        json={"title": "Plain save"},
        headers=AUTH,
    )
    assert response.status_code == 205
    assert db.review_update is None


def test_create_persists_the_list_fields():
    client, db = _client()
    author_uuid = "9f2a4c1e-1234-4abc-9def-0123456789ab"
    response = client.post(
        "/v2/account/articles",
        json={
            "title": "Full dataset",
            "authors": [{"uuid": author_uuid}],
            "tags": ["kw-1"],
            "categories": ["13431"],
            "references": ["https://example.org"],
        },
        headers=AUTH,
    )
    assert response.status_code == 200
    kwargs = db.insert_kwargs
    assert kwargs["tags"] == [{"tag": "kw-1"}]
    assert kwargs["categories"] == [{"uuid": CATEGORY_UUID}]
    assert kwargs["references"] == [{"url": "https://example.org"}]
    assert len(kwargs["authors"]) == 1 and author_uuid in str(kwargs["authors"][0])


def test_delete_single_file_invalidates_both_storage_caches():
    client, db = _client()
    response = client.delete(
        f"/v2/account/articles/{DATASET_UUID}/files/{'f' * 36}", headers=AUTH
    )
    assert response.status_code == 204
    assert "acct-1_storage" in db.cache.invalidated
    assert "ds-1_dataset_storage" in db.cache.invalidated


def test_remove_all_files_clears_the_file_list():
    client, db = _client()
    response = client.request(
        "DELETE",
        f"/v2/account/articles/{DATASET_UUID}/files",
        json={"remove_all": True},
        headers=AUTH,
    )
    assert response.status_code == 204
    assert db.deleted_all == ("dataset:ds-1", "files")
    assert "acct-1_storage" in db.cache.invalidated
    assert "ds-1_dataset_storage" in db.cache.invalidated


def test_remove_all_files_requires_the_flag():
    client, db = _client()
    response = client.request(
        "DELETE",
        f"/v2/account/articles/{DATASET_UUID}/files",
        json={},
        headers=AUTH,
    )
    assert response.status_code == 400
    assert db.deleted_all is None
