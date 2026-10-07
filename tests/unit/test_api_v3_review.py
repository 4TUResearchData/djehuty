"""Contract tests for the v3 field-level review conversation API.

A fake ``db`` provides the RDF-side lookups; a real SQLite ``SqlDatabase`` backs
the conversation store. Covers feature gating, author/reviewer visibility, the
comment flow, institutional scoping, submit validation, and approve dispatch.
"""

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from djehuty.api.services.review.schema import metadata
from djehuty.application import create_app
from djehuty.web.config import config

CONTAINER = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
AUTHOR = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

DATASET = {
    "uuid": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "container_uuid": CONTAINER,
    "account_uuid": AUTHOR,
    "group_id": 10,
    "uri": "dataset:xyz",
    "review_uri": "review:xyz",
    "title": "Coastal temperatures",
    "container_doi": "10.0/abc",
}

ACCOUNTS = {
    "revtoken": {"uuid": "rev-uuid", "group_id": None, "email": "rev@x.y"},
    "insttoken": {"uuid": "inst-uuid", "group_id": 10, "email": "inst@x.y"},
    "inst2token": {"uuid": "inst2-uuid", "group_id": 99, "email": "i2@x.y"},
    "authtoken": {"uuid": AUTHOR, "group_id": 10, "email": "auth@x.y"},
}


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _DB:
    cache = _Cache()

    def account_by_session_token(self, token):
        return ACCOUNTS.get(token)

    def account_by_uuid(self, uuid):
        return next((a for a in ACCOUNTS.values() if a["uuid"] == uuid), None)

    def may_review(self, token, account=None):
        return token == "revtoken"

    def may_review_institution(self, token, account=None):
        return token in ("insttoken", "inst2token")

    def may_impersonate(self, token, account=None):
        return False

    def datasets(self, **kwargs):
        if kwargs.get("container_uuid") in (CONTAINER, None) or kwargs.get("dataset_id"):
            return [dict(DATASET)]
        return []

    def reviews(self, **kwargs):
        return [{"assigned_to": "account:rev-uuid"}]

    def update_review(self, *args, **kwargs):
        return True


def _auth(token):
    return {"Authorization": f"token {token}"}


@pytest.fixture
def client(tmp_path):
    saved = (config.enable_dataset_review, config.sql_database_url)
    config.enable_dataset_review = True
    config.sql_database_url = f"sqlite:///{tmp_path / 'review.db'}"
    app = create_app(_DB())
    metadata.create_all(app.state.sql.engine)
    try:
        yield TestClient(app)
    finally:
        app.state.sql.dispose()
        config.enable_dataset_review, config.sql_database_url = saved


def test_feature_off_returns_404(tmp_path):
    saved = (config.enable_dataset_review, config.sql_database_url)
    config.enable_dataset_review = False
    config.sql_database_url = f"sqlite:///{tmp_path / 'off.db'}"
    try:
        app = create_app(_DB())
        resp = TestClient(app).get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("revtoken"))
        assert resp.status_code == 404
    finally:
        config.enable_dataset_review, config.sql_database_url = saved


def test_author_never_sees_pending_but_reviewer_does(client):
    created = client.post(
        f"/v3/datasets/{CONTAINER}/review/comments",
        headers=_auth("revtoken"),
        json={
            "target_type": "scalar",
            "target_key": "title",
            "target_label": "Title",
            "body": "Please clarify the title.",
        },
    )
    assert created.status_code == 201

    reviewer_view = client.get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("revtoken"))
    assert reviewer_view.status_code == 200
    comments = reviewer_view.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["body"] == "Please clarify the title."
    assert comments[0]["target_label"] == "Title"
    assert comments[0]["field_value_snapshot"] == "Coastal temperatures"

    author_view = client.get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("authtoken"))
    assert author_view.status_code == 200
    assert author_view.json()["comments"] == []


def test_edit_and_delete_comment(client):
    cid = client.post(
        f"/v3/datasets/{CONTAINER}/review/comments",
        headers=_auth("revtoken"),
        json={"target_type": "scalar", "target_key": "title", "body": "First."},
    ).json()["id"]

    assert (
        client.patch(
            f"/v3/datasets/{CONTAINER}/review/comments/{cid}",
            headers=_auth("revtoken"),
            json={"body": "Edited with more detail."},
        ).status_code
        == 204
    )
    convo = client.get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("revtoken")).json()
    assert convo["comments"][0]["body"] == "Edited with more detail."
    assert convo["comments"][0]["updated_at"] is not None

    assert (
        client.delete(
            f"/v3/datasets/{CONTAINER}/review/comments/{cid}", headers=_auth("revtoken")
        ).status_code
        == 204
    )
    convo = client.get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("revtoken")).json()
    assert convo["comments"] == []


def test_submit_publishes_open_comments_but_hides_resolved_from_author(client):
    open_cid = client.post(
        f"/v3/datasets/{CONTAINER}/review/comments",
        headers=_auth("revtoken"),
        json={"target_type": "scalar", "target_key": "title", "body": "Clarify."},
    ).json()["id"]
    resolved_cid = client.post(
        f"/v3/datasets/{CONTAINER}/review/comments",
        headers=_auth("revtoken"),
        json={"target_type": "scalar", "target_key": "description", "body": "Typo."},
    ).json()["id"]

    assert (
        client.post(
            f"/v3/datasets/{CONTAINER}/review/comments/{open_cid}/replies",
            headers=_auth("authtoken"),
            json={"body": "Clarified."},
        ).status_code
        == 201
    )
    # The reviewer resolves the second comment -- it is closed.
    assert (
        client.post(
            f"/v3/datasets/{CONTAINER}/review/comments/{resolved_cid}/resolve",
            headers=_auth("revtoken"),
            json={"resolved": True},
        ).status_code
        == 204
    )

    # Submit request-changes publishes the round.
    submitted = client.post(
        f"/v3/datasets/{CONTAINER}/review/submit",
        headers=_auth("revtoken"),
        json={"outcome": "request_changes", "general_notes": "Thanks."},
    )
    assert submitted.status_code == 200

    # The author sees only the still-open comment, never the resolved one or internal notes.
    author_view = client.get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("authtoken")).json()
    assert {c["id"] for c in author_view["comments"]} == {open_cid}
    assert "internal_notes" not in author_view["rounds"][0]

    # The reviewer still sees both, including the resolved one.
    reviewer_view = client.get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("revtoken")).json()
    assert {c["id"] for c in reviewer_view["comments"]} == {open_cid, resolved_cid}
    assert any(
        c["id"] == resolved_cid and c["reviewer_resolved"] for c in reviewer_view["comments"]
    )


def test_author_reply_can_be_edited_and_deleted_by_its_author(client):
    cid = client.post(
        f"/v3/datasets/{CONTAINER}/review/comments",
        headers=_auth("revtoken"),
        json={"target_type": "scalar", "target_key": "title", "body": "Clarify."},
    ).json()["id"]
    reply_id = client.post(
        f"/v3/datasets/{CONTAINER}/review/comments/{cid}/replies",
        headers=_auth("authtoken"),
        json={"body": "First reply."},
    ).json()["id"]

    assert (
        client.patch(
            f"/v3/datasets/{CONTAINER}/review/comments/{cid}/replies/{reply_id}",
            headers=_auth("authtoken"),
            json={"body": "Edited reply."},
        ).status_code
        == 204
    )
    convo = client.get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("revtoken")).json()
    replies = [e for e in convo["comments"][0]["events"] if e["kind"] == "reply"]
    assert replies[0]["body"] == "Edited reply."

    # The reviewer cannot delete the author's reply (not their own) ...
    client.delete(
        f"/v3/datasets/{CONTAINER}/review/comments/{cid}/replies/{reply_id}",
        headers=_auth("revtoken"),
    )
    convo = client.get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("revtoken")).json()
    assert [e for e in convo["comments"][0]["events"] if e["kind"] == "reply"]
    # ... but the author can.
    assert (
        client.delete(
            f"/v3/datasets/{CONTAINER}/review/comments/{cid}/replies/{reply_id}",
            headers=_auth("authtoken"),
        ).status_code
        == 204
    )
    convo = client.get(f"/v3/datasets/{CONTAINER}/review", headers=_auth("revtoken")).json()
    assert [e for e in convo["comments"][0]["events"] if e["kind"] == "reply"] == []


def test_institutional_reviewer_out_of_group_is_forbidden(client):
    resp = client.post(
        f"/v3/datasets/{CONTAINER}/review/comments",
        headers=_auth("inst2token"),
        json={"target_type": "scalar", "target_key": "title", "body": "x"},
    )
    assert resp.status_code == 403
    # An institutional reviewer in the dataset's group is allowed.
    ok = client.post(
        f"/v3/datasets/{CONTAINER}/review/comments",
        headers=_auth("insttoken"),
        json={"target_type": "scalar", "target_key": "title", "body": "x"},
    )
    assert ok.status_code == 201


def test_submit_request_changes_requires_a_comment_or_notes(client):
    resp = client.post(
        f"/v3/datasets/{CONTAINER}/review/submit",
        headers=_auth("revtoken"),
        json={"outcome": "request_changes"},
    )
    assert resp.status_code == 400


def test_submit_approve_dispatches_to_perform_publish(client, monkeypatch):
    calls = {}

    def fake_perform_publish(db, account, dataset, reviewer_account, dataset_id):
        calls["account"] = account
        calls["reviewer"] = reviewer_account
        return JSONResponse(content={"location": "ok"}, status_code=201)

    monkeypatch.setattr("djehuty.api.v3.datasets.publishing._perform_publish", fake_perform_publish)
    resp = client.post(
        f"/v3/datasets/{CONTAINER}/review/submit",
        headers=_auth("revtoken"),
        json={"outcome": "approve"},
    )
    assert resp.status_code == 201
    assert calls["account"]["uuid"] == AUTHOR  # published as the dataset owner
    assert calls["reviewer"]["uuid"] == "rev-uuid"  # assigned the acting reviewer


def test_author_reply_without_ownership_is_forbidden(client):
    cid = client.post(
        f"/v3/datasets/{CONTAINER}/review/comments",
        headers=_auth("revtoken"),
        json={"target_type": "scalar", "target_key": "title", "body": "Clarify."},
    ).json()["id"]
    # A stranger (no reviewer rights, not the owner) cannot reply.
    ACCOUNTS["strangertoken"] = {"uuid": "stranger", "group_id": None, "email": "s@x.y"}
    try:
        resp = client.post(
            f"/v3/datasets/{CONTAINER}/review/comments/{cid}/replies",
            headers=_auth("strangertoken"),
            json={"body": "hi"},
        )
        assert resp.status_code == 403
    finally:
        ACCOUNTS.pop("strangertoken", None)
