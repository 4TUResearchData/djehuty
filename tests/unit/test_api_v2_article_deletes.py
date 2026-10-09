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
    def __init__(self, files=None, fundings=None, category=None, soft_delete_result=True):
        self.cache = _Cache()
        self._files = files or []
        self._fundings = fundings or []
        self._category = category
        self._soft_delete_result = soft_delete_result
        self.deleted = None
        self.updated = None
        self.soft_deleted = None
        self.hard_deleted = None

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

    def soft_delete_dataset_draft(self, container_uuid, dataset_uuid, account_uuid, owner_uuid):
        self.soft_deleted = (container_uuid, dataset_uuid, account_uuid, owner_uuid)
        return self._soft_delete_result

    def delete_dataset_draft(self, *args, **kwargs):
        self.hard_deleted = args
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


def test_delete_absent_author_is_500():
    # AS-IS: legacy raises StopIteration on a missing author -> 500.
    db = _Db()
    response = _client(db).delete(
        f"/v2/account/articles/{DATASET_UUID}/authors/{'x' * 36}", headers=AUTH
    )
    assert response.status_code == 500
    assert db.updated is None


def test_delete_funding_absent_from_a_non_empty_list_is_500():
    # AS-IS: legacy raises StopIteration when the id isn't present -> 500.
    db = _Db(fundings=[{"uuid": "other"}])
    response = _client(db).delete(
        f"/v2/account/articles/{DATASET_UUID}/funding/{'x' * 36}", headers=AUTH
    )
    assert response.status_code == 500
    assert db.updated is None


def test_get_absent_file_is_500():
    # AS-IS: legacy dereferences a missing file (None) -> 500.
    db = _Db(files=[])
    response = _client(db).get(
        f"/v2/account/articles/{DATASET_UUID}/files/{FILE_UUID}", headers=AUTH
    )
    assert response.status_code == 500


def test_delete_dataset_soft_deletes_the_draft():
    db = _Db()
    response = _client(db).delete(f"/v2/account/articles/{DATASET_UUID}", headers=AUTH)
    assert response.status_code == 204
    assert db.soft_deleted == (DATASET_UUID, "ds-1", "acct-1", "acct-1")
    assert db.hard_deleted is None


def test_delete_dataset_failed_soft_delete_is_500():
    db = _Db(soft_delete_result=False)
    response = _client(db).delete(f"/v2/account/articles/{DATASET_UUID}", headers=AUTH)
    assert response.status_code == 500
