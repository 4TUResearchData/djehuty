"""Collaborative-permission enforcement on /v2/account/articles metadata routes.

Regression test for GHSA-3gh2-4q87-wcjx. The contract:

* reads require ``metadata_read``;
* writes require ``metadata_edit``;
* private-link routes are owner-only;
* the owner is never affected.
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app

DATASET = "a" * 36
CHILD = "c" * 36
AUTH = {"Authorization": "tok"}

NONE = {
    "metadata_read": False,
    "metadata_edit": False,
    "metadata_remove": False,
    "data_read": False,
    "data_edit": False,
    "data_remove": False,
}
CAN_READ = {**NONE, "metadata_read": True}
CAN_EDIT = {**CAN_READ, "metadata_edit": True}


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _Db:
    def __init__(self, shared, perms):
        self.cache = _Cache()
        self._shared = shared
        self._perms = perms
        self.writes = []

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

    def is_depositor(self, token, account):
        return True

    def category_by_id(self, **kwargs):
        return {"uuid": CHILD}

    def license_url_by_id(self, license_id):
        return None

    # Record every mutating call so a denied request can be shown to persist
    # nothing.
    def update_dataset(self, *a, **k):
        self.writes.append("update_dataset")
        return True

    def update_item_list(self, *a, **k):
        self.writes.append("update_item_list")
        return True

    def delete_item_from_list(self, *a, **k):
        self.writes.append("delete_item_from_list")
        return True

    def delete_dataset_embargo(self, *a, **k):
        self.writes.append("delete_dataset_embargo")
        return True

    def delete_dataset_draft(self, *a, **k):
        self.writes.append("delete_dataset_draft")
        return True

    def insert_private_link(self, *a, **k):
        self.writes.append("insert_private_link")
        return "link:new"

    def update_private_link(self, *a, **k):
        self.writes.append("update_private_link")
        return True

    def delete_private_links(self, *a, **k):
        self.writes.append("delete_private_links")
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client(shared, perms):
    db = _Db(shared, perms)
    return TestClient(create_app(db)), db


# Each row: (label, http_method, path, json_body, required_permission).
# required_permission is "read" (metadata_read), "edit" (metadata_edit) or
# "owner" (owner-only; no collaborator flag ever grants it).
ROUTES = [
    ("get_article", "GET", f"/v2/account/articles/{DATASET}", None, "read"),
    ("update_article", "PUT", f"/v2/account/articles/{DATASET}", {"title": "x" * 3}, "edit"),
    ("delete_article", "DELETE", f"/v2/account/articles/{DATASET}", None, "edit"),
    ("list_authors", "GET", f"/v2/account/articles/{DATASET}/authors", None, "read"),
    ("replace_authors", "PUT", f"/v2/account/articles/{DATASET}/authors", {"authors": []}, "edit"),
    ("add_authors", "POST", f"/v2/account/articles/{DATASET}/authors", {"authors": []}, "edit"),
    (
        "delete_author",
        "DELETE",
        f"/v2/account/articles/{DATASET}/authors/{CHILD}",
        None,
        "edit",
    ),
    ("list_categories", "GET", f"/v2/account/articles/{DATASET}/categories", None, "read"),
    (
        "replace_categories",
        "PUT",
        f"/v2/account/articles/{DATASET}/categories",
        {"categories": []},
        "edit",
    ),
    (
        "add_categories",
        "POST",
        f"/v2/account/articles/{DATASET}/categories",
        {"categories": []},
        "edit",
    ),
    (
        "delete_category",
        "DELETE",
        f"/v2/account/articles/{DATASET}/categories/{CHILD}",
        None,
        "edit",
    ),
    ("get_embargo", "GET", f"/v2/account/articles/{DATASET}/embargo", None, "read"),
    ("delete_embargo", "DELETE", f"/v2/account/articles/{DATASET}/embargo", None, "edit"),
    ("list_funding", "GET", f"/v2/account/articles/{DATASET}/funding", None, "read"),
    ("replace_funding", "PUT", f"/v2/account/articles/{DATASET}/funding", {"funders": []}, "edit"),
    ("add_funding", "POST", f"/v2/account/articles/{DATASET}/funding", {"funders": []}, "edit"),
    (
        "delete_funding",
        "DELETE",
        f"/v2/account/articles/{DATASET}/funding/{CHILD}",
        None,
        "edit",
    ),
    ("reserve_doi", "POST", f"/v2/account/articles/{DATASET}/reserve_doi", {}, "edit"),
    # Private links: owner-only in the legacy stack.
    ("list_private_links", "GET", f"/v2/account/articles/{DATASET}/private_links", None, "owner"),
    (
        "create_private_link",
        "POST",
        f"/v2/account/articles/{DATASET}/private_links",
        {},
        "owner",
    ),
    (
        "get_private_link",
        "GET",
        f"/v2/account/articles/{DATASET}/private_links/{CHILD}",
        None,
        "owner",
    ),
    (
        "update_private_link",
        "PUT",
        f"/v2/account/articles/{DATASET}/private_links/{CHILD}",
        {},
        "owner",
    ),
    (
        "delete_private_link",
        "DELETE",
        f"/v2/account/articles/{DATASET}/private_links/{CHILD}",
        None,
        "owner",
    ),
]


def test_zero_permission_collaborator_denied_everywhere():
    """A collaborator with every flag False gets 403 on every metadata route."""
    for label, method, path, body, _perm in ROUTES:
        client, db = _client(shared=True, perms=NONE)
        response = client.request(method, path, json=body, headers=AUTH)
        assert response.status_code == 403, f"{label}: expected 403, got {response.status_code}"
        assert db.writes == [], f"{label}: a denied request persisted {db.writes}"


def test_owner_is_never_blocked():
    """The owner (dataset not shared with them) is admitted on every route."""
    for label, method, path, body, _perm in ROUTES:
        client, _ = _client(shared=False, perms=NONE)
        response = client.request(method, path, json=body, headers=AUTH)
        assert response.status_code != 403, f"{label}: owner wrongly blocked"


def test_read_only_collaborator_can_read_metadata_but_not_write():
    """metadata_read opens reads; writes still require metadata_edit."""
    for label, method, path, body, perm in ROUTES:
        if perm != "read":
            continue
        client, _ = _client(shared=True, perms=CAN_READ)
        response = client.request(method, path, json=body, headers=AUTH)
        assert response.status_code != 403, f"{label}: read denied with metadata_read"

    for label, method, path, body, perm in ROUTES:
        if perm != "edit":
            continue
        client, db = _client(shared=True, perms=CAN_READ)
        response = client.request(method, path, json=body, headers=AUTH)
        assert response.status_code == 403, f"{label}: write allowed with only metadata_read"
        assert db.writes == [], f"{label}: denied write persisted {db.writes}"


def test_metadata_edit_collaborator_can_write():
    """metadata_edit opens every metadata write (but not owner-only routes)."""
    for label, method, path, body, perm in ROUTES:
        if perm != "edit":
            continue
        client, _ = _client(shared=True, perms=CAN_EDIT)
        response = client.request(method, path, json=body, headers=AUTH)
        assert response.status_code != 403, f"{label}: write denied with metadata_edit"


def test_private_links_are_owner_only():
    """Even a fully-privileged collaborator is denied on the private-link routes."""
    full = {key: True for key in NONE}
    for label, method, path, body, perm in ROUTES:
        if perm != "owner":
            continue
        client, db = _client(shared=True, perms=full)
        response = client.request(method, path, json=body, headers=AUTH)
        assert response.status_code == 403, f"{label}: collaborator reached an owner-only route"
        assert db.writes == [], f"{label}: owner-only route persisted {db.writes}"
