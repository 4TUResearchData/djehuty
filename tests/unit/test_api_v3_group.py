"""The api-v3 group is registered and mounted, and its handlers call the same
db methods with the same shapes as the legacy handlers.

Verifies /v3/ resolves to the new stack, respects a legacy override, and pins
the side-effect call shapes that the port previously got wrong (collaborator
db signatures, reviewer-privilege token argument, the process-wide lock, the
git_url formatter argument). The full AS-IS behaviour of the endpoints is
covered by the e2e API contract suite (tests/e2e/tests/api/v3).
"""

from fastapi.testclient import TestClient

from djehuty.application import create_app
from djehuty.route_groups import group_for_path, target_for_path


def test_v3_paths_resolve_to_new_by_default():
    assert group_for_path("/v3/datasets").name == "api-v3"
    assert target_for_path("/v3/datasets", default="new", overrides={}) == "new"


def test_v3_can_be_pinned_to_legacy():
    assert (
        target_for_path("/v3/datasets", default="new", overrides={"api-v3": "legacy"}) == "legacy"
    )


class _FakeDB:
    """A permissive db double: unknown methods return an empty list."""

    def __init__(self):
        self.calls = []

    def account_by_session_token(self, token):
        return None

    def __getattr__(self, name):
        def _record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return []

        return _record


class _AuthDB(_FakeDB):
    """Authenticates the token "good"; grants no reviewer/admin privileges."""

    def account_by_session_token(self, token):
        return {"uuid": "a1", "email": "x", "group_id": 28586} if token == "good" else None


_AUTH = {"Authorization": "good"}

# Valid UUIDs: the collaborator handlers 404 on anything that isn't one.
_DATASET_UUID = "27e6a01d-3f09-4d90-ae02-1d749ae9efb8"
_COLLAB_UUID = "84cae99f-a691-4af2-9d21-f5c0817c26df"


def test_umbrella_mounts_v3_endpoints():
    client = TestClient(create_app(_FakeDB()))
    # A public v3 endpoint resolves (200), proving the router is mounted.
    assert client.get("/v3/groups").status_code == 200


def test_v3_is_documented_in_the_openapi_spec():
    spec = TestClient(create_app(_FakeDB())).get("/api/openapi.json").json()
    v3_paths = [p for p in spec["paths"] if p.startswith("/v3")]
    assert len(v3_paths) > 40


# --- Collaborators: the port used to crash on non-existent db kwargs ---------


class _CollabDB(_AuthDB):
    def datasets(self, *args, **kwargs):
        self.calls.append(("datasets", args, kwargs))
        return [
            {
                "uuid": "d-uuid",
                "container_uuid": _DATASET_UUID,
                "uri": "dataset:d-uuid",
                "account_uuid": "a1",
            }
        ]

    def collaborators(self, *args, **kwargs):
        self.calls.append(("collaborators", args, kwargs))
        return [{"account_uuid": "a1", "is_supervisor": True, "uuid": _COLLAB_UUID}]

    def update_collaborator(self, *args, **kwargs):
        self.calls.append(("update_collaborator", args, kwargs))
        return True

    def delete_collaborator(self, *args, **kwargs):
        self.calls.append(("delete_collaborator", args, kwargs))
        return True

    def item_collaborative_permissions(self, *args, **kwargs):
        return {}


def _last_call(db, name):
    return next(c for c in reversed(db.calls) if c[0] == name)


def test_list_collaborators_is_unfiltered_by_account():
    # AS-IS: legacy calls db.collaborators(dataset_uuid) with no account filter,
    # so the whole list is returned, not just the caller's own row.
    db = _CollabDB()
    client = TestClient(create_app(db))
    resp = client.get(f"/v3/datasets/{_DATASET_UUID}/collaborators", headers=_AUTH)
    assert resp.status_code == 200
    _, args, kwargs = _last_call(db, "collaborators")
    assert "account_uuid" not in kwargs
    assert args == ("d-uuid",)


def test_update_collaborator_uses_legacy_positional_signature():
    db = _CollabDB()
    client = TestClient(create_app(db))
    body = {
        "metadata": {"read": True, "edit": True},
        "data": {"read": True, "edit": False, "remove": False},
    }
    resp = client.put(
        f"/v3/datasets/{_DATASET_UUID}/collaborators/{_COLLAB_UUID}", json=body, headers=_AUTH
    )
    assert resp.status_code == 204
    _, args, kwargs = _last_call(db, "update_collaborator")
    # Legacy positional signature: dataset_uuid, collaborator_uuid, then the
    # six booleans. No keyword arguments the db layer does not accept.
    assert kwargs == {}
    assert args == ("d-uuid", _COLLAB_UUID, True, True, False, True, False, False)


def test_delete_collaborator_uses_legacy_positional_signature():
    db = _CollabDB()
    client = TestClient(create_app(db))
    resp = client.delete(
        f"/v3/datasets/{_DATASET_UUID}/collaborators/{_COLLAB_UUID}", headers=_AUTH
    )
    assert resp.status_code == 204
    _, args, kwargs = _last_call(db, "delete_collaborator")
    assert kwargs == {}
    assert args == ("d-uuid", _COLLAB_UUID)


# --- Reviews: privilege checks must pass the token, not an account UUID ------


class _ReviewerDB(_AuthDB):
    def __init__(self):
        super().__init__()
        self.may_review_args = []

    def may_review(self, token):
        self.may_review_args.append(token)
        return token == "good"

    def may_review_institution(self, token):
        return False

    def reviews(self, *args, **kwargs):
        self.calls.append(("reviews", args, kwargs))
        return []

    def reviewer_accounts(self):
        return [{"uuid": "r1"}]

    def institutional_reviewer_accounts(self):
        return [{"uuid": "r2"}]


def test_reviews_privilege_check_receives_the_session_token():
    db = _ReviewerDB()
    client = TestClient(create_app(db))
    resp = client.get("/v3/reviews", headers=_AUTH)
    assert resp.status_code == 200
    # may_review must have been called with the raw session token, never an
    # account UUID (which would always resolve to False -> permanent 403).
    assert "good" in db.may_review_args
    assert "a1" not in db.may_review_args
    # Legacy queries the full review list (limit=10000), not the caller's own.
    _, _, kwargs = _last_call(db, "reviews")
    assert kwargs.get("limit") == 10000


def test_reviewers_includes_institutional_reviewers():
    db = _ReviewerDB()
    client = TestClient(create_app(db))
    resp = client.get("/v3/reviewers", headers=_AUTH)
    assert resp.status_code == 200
    uuids = {r["uuid"] for r in resp.json()}
    assert uuids == {"r1", "r2"}


def test_reviews_forbidden_without_privileges():
    class _NoPriv(_AuthDB):
        def may_review(self, token):
            return False

        def may_review_institution(self, token):
            return False

    client = TestClient(create_app(_NoPriv()))
    assert client.get("/v3/reviews", headers=_AUTH).status_code == 403


# --- Locks: one process-wide instance, not re-created per request ------------


def test_submit_and_upload_share_one_process_lock_instance():
    from djehuty.api.v3.datasets import files, publishing

    # Both modules bind a module-level Locks() at import. Because Locks is a
    # singleton, they must be the very same object; a per-request Locks() would
    # re-run __init__ and replace the held lock objects.
    assert files._process_locks is publishing._process_locks
    assert files._process_locks.locks is publishing._process_locks.locks


# --- Git: upload-pack records a gitDownload event ----------------------------


def test_upload_pack_gate_records_a_gitdownload_event():
    from djehuty.api.v3 import git

    class _GitDB(_FakeDB):
        def datasets(self, *args, **kwargs):
            self.calls.append(("datasets", args, kwargs))
            return [{"container_uuid": _DATASET_UUID}]

        def insert_log_entry(self, *args, **kwargs):
            self.calls.append(("insert_log_entry", args, kwargs))
            return True

    db = _GitDB()

    class _Req:
        headers = {"x-forwarded-for": "203.0.113.7"}
        client = None

    git._upload_pack_gate(db, _Req(), _DATASET_UUID)

    name, args, kwargs = _last_call(db, "insert_log_entry")
    # gitDownload event, keyed to the resolved container, from the fetch's IP.
    assert kwargs.get("event_type") == "gitDownload"
    assert kwargs.get("item_type") == "dataset"
    assert _DATASET_UUID in args
    assert "203.0.113.7" in args


# --- codemeta / ro-crates pass git_url to the formatter ----------------------


class _SoftwareDB(_FakeDB):
    def datasets(self, *args, **kwargs):
        return [
            {
                "uri": "dataset:d",
                "container_uuid": _DATASET_UUID,
                "defined_type_name": "software",
                "git_uuid": "no-such-repo",
                "doi": "10.4121/x",
            }
        ]


# --- Publish: the reviewer impersonator flow assigns and publishes ----------


class _PublishDB(_FakeDB):
    def account_by_session_token(self, token):
        if token == "rev":
            return {"uuid": "rev1", "email": "rev@x", "group_id": 1}
        if token == "depositor":
            return {"uuid": "a1", "email": "owner@x", "group_id": 1}
        return None

    def account_by_uuid(self, uuid):
        return {"uuid": uuid, "email": "owner@x"}

    def may_review(self, token):
        return token == "rev"

    def may_review_institution(self, token):
        return False

    def datasets(self, *args, **kwargs):
        return [
            {
                "uuid": "d",
                "container_uuid": "c",
                "account_uuid": "a1",
                "uri": "dataset:d",
                "title": "T",
                "review_uri": "review:r",
                "group_id": 1,
                "container_doi": "10.x/c",
                "doi": "10.x/d.v1",
            }
        ]

    def container(self, *args, **kwargs):
        return {"latest_published_version_number": 0}

    def update_review(self, *args, **kwargs):
        self.calls.append(("update_review", args, kwargs))
        return True

    def publish_dataset(self, *args, **kwargs):
        self.calls.append(("publish_dataset", args, kwargs))
        return True


def test_publish_reviewer_flow_assigns_and_publishes():
    db = _PublishDB()
    client = TestClient(create_app(db))
    # Reviewer flow: the impersonator cookie carries the reviewer session; the
    # regular session cookie is the impersonated depositor.
    client.cookies.set("impersonator_djehuty_session", "rev")
    client.cookies.set("djehuty_session", "depositor")
    resp = client.post(f"/v3/datasets/{_DATASET_UUID}/publish")
    assert resp.status_code == 201
    assert "/review/published/" in resp.json()["location"]
    # The reviewer is assigned to the review, and the dataset is published.
    _, _, kwargs = _last_call(db, "update_review")
    assert kwargs.get("assigned_to") == "rev1"
    assert any(c[0] == "publish_dataset" for c in db.calls)


def test_publish_forbidden_without_reviewer_privileges():
    db = _PublishDB()
    client = TestClient(create_app(db))
    # A plain depositor session grants no reviewer privileges.
    client.cookies.set("djehuty_session", "depositor")
    assert client.post(f"/v3/datasets/{_DATASET_UUID}/publish").status_code == 403


def test_codemeta_passes_git_url_to_the_formatter(monkeypatch):
    calls = {}

    def _fake_format(record, git_url, *args, **kwargs):
        calls["git_url"] = git_url
        return {}

    # config.storage is unset in the unit environment, so stub the on-disk
    # lookup; the point of this test is that the required positional git_url
    # argument reaches the formatter (its omission was a TypeError 500).
    monkeypatch.setattr(
        "djehuty.api.v3.codemeta.repository_url_for_dataset", lambda dataset: "git://url"
    )
    monkeypatch.setattr(
        "djehuty.api.v3.codemeta.formatter.format_codemeta_record", _fake_format
    )
    client = TestClient(create_app(_SoftwareDB()))
    resp = client.get("/v3/codemeta")
    assert resp.status_code == 200
    assert calls.get("git_url") == "git://url"


# --- Search: the term must reach db.datasets structured, not as a raw string --


class _SearchDB(_FakeDB):
    """Records the search_for shape db.datasets is called with."""

    def datasets(self, *args, **kwargs):
        self.calls.append(("datasets", args, kwargs))
        return []


def test_datasets_search_passes_structured_search_for():
    # Regression: the legacy /search page calls POST /v3/datasets/search, and
    # db.datasets expects search_for as the structured per-field token list that
    # parse_search_terms builds. Passing the raw string made the full-text
    # filter a no-op, so every search returned all datasets (a gibberish query
    # matched seed data). Assert the port hands db.datasets the structured form,
    # identical to what the legacy handler builds.
    from djehuty.utils.convenience import parse_search_terms

    db = _SearchDB()
    client = TestClient(create_app(db))
    term = 'wind "sea level"'
    resp = client.post("/v3/datasets/search", json={"search_for": term})
    assert resp.status_code == 200
    _, _, kwargs = _last_call(db, "datasets")
    search_for = kwargs.get("search_for")
    assert isinstance(search_for, list), f"search_for must be structured, got {type(search_for)}"
    assert search_for == parse_search_terms(term)


def test_datasets_search_none_term_stays_none():
    # No search term → no full-text filter; must not become an empty structure
    # that would filter everything out.
    db = _SearchDB()
    client = TestClient(create_app(db))
    resp = client.post("/v3/datasets/search", json={"limit": 10})
    assert resp.status_code == 200
    _, _, kwargs = _last_call(db, "datasets")
    assert kwargs.get("search_for") is None


# --- Tags: the full list must be read before the wholesale write-back --------


class _TagsDB(_AuthDB):
    """Records the limit db.tags is read with; item_collaborative gives access."""

    def datasets(self, *args, **kwargs):
        return [{"uuid": "d", "container_uuid": _DATASET_UUID, "uri": "dataset:d"}]

    def tags(self, *args, **kwargs):
        self.calls.append(("tags", args, kwargs))
        return []

    def update_item_list(self, *args, **kwargs):
        self.calls.append(("update_item_list", args, kwargs))
        return True

    def item_collaborative_permissions(self, *args, **kwargs):
        return {}


def test_dataset_tags_add_reads_full_existing_list():
    # Regression: db.update_item_list REPLACES the whole tag list, so the
    # pre-write read must not be capped at the default limit=10 — that silently
    # drops tags 11+ on every add.
    db = _TagsDB()
    client = TestClient(create_app(db))
    resp = client.post(
        f"/v3/datasets/{_DATASET_UUID}/tags", json={"tags": ["new"]}, headers=_AUTH
    )
    assert resp.status_code == 205
    _, _, kwargs = _last_call(db, "tags")
    assert kwargs.get("limit") == 10000


def test_dataset_tags_delete_reads_full_existing_list():
    db = _TagsDB()
    client = TestClient(create_app(db))
    resp = client.delete(f"/v3/datasets/{_DATASET_UUID}/tags", params={"tag": "sometag"}, headers=_AUTH)
    assert resp.status_code == 204
    _, _, kwargs = _last_call(db, "tags")
    assert kwargs.get("limit") == 10000
