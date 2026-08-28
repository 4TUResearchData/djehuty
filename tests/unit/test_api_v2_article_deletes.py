"""Unit tests for /v2/account/articles sub-resource delete status codes.

Pins parity with legacy: deleting an absent file, or funding from an empty list,
returns 404, and deleting an unresolvable category returns 403 — rather than a
blanket 204.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app

DATASET_UUID = "a" * 36
FILE_UUID = "f" * 36
CATEGORY_UUID = "d" * 36
AUTH = {"Authorization": "good"}


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _Db:
    def __init__(self, files=None, fundings=None, category=None):
        self.cache = _Cache()
        self._files = files or []
        self._fundings = fundings or []
        self._category = category
        self.deleted = None
        self.updated = None

    def account_by_session_token(self, token):
        return {"uuid": "acct-1", "email": "x"} if token == "good" else None

    def datasets(self, **kwargs):
        return [
            {
                "uuid": "ds-1",
                "uri": "dataset:ds-1",
                "container_uuid": DATASET_UUID,
                "account_uuid": "acct-1",
            }
        ]

    def dataset_files(self, **kwargs):
        return self._files

    def fundings(self, **kwargs):
        return self._fundings

    def category_by_id(self, **kwargs):
        return self._category

    def delete_item_from_list(self, subject, predicate, value):
        self.deleted = (subject, predicate, value)
        return True

    def update_item_list(self, item_uuid, account_uuid, items, predicate):
        self.updated = (item_uuid, account_uuid, list(items), predicate)
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client(db):
    return TestClient(create_app(db))


def test_delete_absent_file_is_404():
    db = _Db(files=[])
    response = _client(db).delete(
        f"/v2/account/articles/{DATASET_UUID}/files/{FILE_UUID}", headers=AUTH
    )
    assert response.status_code == 404
    assert db.deleted is None


def test_delete_present_file_is_204():
    db = _Db(files=[{"uuid": FILE_UUID}])
    response = _client(db).delete(
        f"/v2/account/articles/{DATASET_UUID}/files/{FILE_UUID}", headers=AUTH
    )
    assert response.status_code == 204
    assert db.deleted is not None


def test_delete_funding_without_any_is_404():
    db = _Db(fundings=[])
    response = _client(db).delete(f"/v2/account/articles/{DATASET_UUID}/funding/1", headers=AUTH)
    assert response.status_code == 404
    assert db.updated is None


def test_delete_unresolvable_category_is_403():
    db = _Db(category=None)
    response = _client(db).delete(
        f"/v2/account/articles/{DATASET_UUID}/categories/Environment", headers=AUTH
    )
    assert response.status_code == 403
    assert db.deleted is None


def test_delete_resolvable_category_is_204():
    db = _Db(category={"uuid": CATEGORY_UUID})
    response = _client(db).delete(
        f"/v2/account/articles/{DATASET_UUID}/categories/13431", headers=AUTH
    )
    assert response.status_code == 204
    assert db.deleted is not None
