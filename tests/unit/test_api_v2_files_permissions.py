"""Unit tests for collaborative-permission enforcement on /v2 file endpoints.

A collaborator must hold the right permission for each operation on a dataset
shared with them (``data_read`` to list/read, ``data_edit`` to add, and
``data_remove`` to delete); the owner (for whom the dataset is not "shared") is
unaffected.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app

DATASET = "a" * 36
FILE = "f" * 36
AUTH = {"Authorization": "tok"}

READ_ONLY = {
    "metadata_read": True,
    "metadata_edit": False,
    "metadata_remove": False,
    "data_read": True,
    "data_edit": False,
    "data_remove": False,
}
CAN_REMOVE = {**READ_ONLY, "data_remove": True}
CAN_EDIT = {**READ_ONLY, "data_edit": True}
NO_DATA = {**READ_ONLY, "data_read": False}


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _Db:
    def __init__(self, shared, perms):
        self.cache = _Cache()
        self._shared = shared
        self._perms = perms
        self.deleted = []

    def account_by_session_token(self, token):
        return {"uuid": "caller-1", "email": "caller@example.org"} if token == "tok" else None

    def datasets(self, **kwargs):
        return [
            {
                "uuid": "ds-1",
                "container_uuid": DATASET,
                "uri": "dataset:ds-1",
                "account_uuid": "owner-1",
                "is_shared_with_me": self._shared,
            }
        ]

    def item_collaborative_permissions(self, item_type, item_uuid, account_uuid):
        return self._perms

    def dataset_files(self, **kwargs):
        return [{"uuid": FILE, "container_uuid": DATASET}]

    def delete_item_from_list(self, *a, **k):
        self.deleted.append("one")
        return True

    def delete_items_all_from_list(self, *a, **k):
        self.deleted.append("all")
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client(shared, perms):
    db = _Db(shared, perms)
    return TestClient(create_app(db)), db


def test_single_delete_denied_for_read_only_collaborator():
    client, db = _client(shared=True, perms=READ_ONLY)
    response = client.delete(f"/v2/account/articles/{DATASET}/files/{FILE}", headers=AUTH)
    assert response.status_code == 403
    assert db.deleted == []


def test_remove_all_denied_for_read_only_collaborator():
    client, db = _client(shared=True, perms=READ_ONLY)
    response = client.request(
        "DELETE",
        f"/v2/account/articles/{DATASET}/files",
        json={"remove_all": True},
        headers=AUTH,
    )
    assert response.status_code == 403
    assert db.deleted == []


def test_single_delete_allowed_for_owner():
    client, db = _client(shared=False, perms=READ_ONLY)
    response = client.delete(f"/v2/account/articles/{DATASET}/files/{FILE}", headers=AUTH)
    assert response.status_code == 204
    assert db.deleted == ["one"]


def test_single_delete_allowed_for_collaborator_with_data_remove():
    client, db = _client(shared=True, perms=CAN_REMOVE)
    response = client.delete(f"/v2/account/articles/{DATASET}/files/{FILE}", headers=AUTH)
    assert response.status_code == 204
    assert db.deleted == ["one"]


def test_list_files_denied_without_data_read():
    client, _ = _client(shared=True, perms=NO_DATA)
    response = client.get(f"/v2/account/articles/{DATASET}/files", headers=AUTH)
    assert response.status_code == 403


def test_get_file_denied_without_data_read():
    client, _ = _client(shared=True, perms=NO_DATA)
    response = client.get(f"/v2/account/articles/{DATASET}/files/{FILE}", headers=AUTH)
    assert response.status_code == 403


def test_create_file_denied_without_data_edit():
    client, _ = _client(shared=True, perms=READ_ONLY)
    response = client.post(
        f"/v2/account/articles/{DATASET}/files",
        json={"link": "https://example.org/d"},
        headers=AUTH,
    )
    assert response.status_code == 403


def test_list_files_allowed_with_data_read():
    client, _ = _client(shared=True, perms=READ_ONLY)
    response = client.get(f"/v2/account/articles/{DATASET}/files", headers=AUTH)
    assert response.status_code == 200


def test_create_file_allowed_with_data_edit():
    client, _ = _client(shared=True, perms=CAN_EDIT)
    response = client.post(
        f"/v2/account/articles/{DATASET}/files",
        json={"link": "https://example.org/d"},
        headers=AUTH,
    )
    assert response.status_code == 201
