"""The reviewer read-only page (/review/dataset/<id>): gating, render, auth."""

import pytest
from fastapi.testclient import TestClient

from djehuty.application import create_app
from djehuty.web.config import config

DS = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

DATASET = {
    "uuid": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "container_uuid": DS,
    "account_uuid": "author-uuid",
    "uri": "dataset:x",
    "title": "Coastal temperatures",
    "description": "Measurements",
    "publisher": "TU Delft",
}
REVIEWER = {"uuid": "rev-uuid", "group_id": None, "email": "r@x.y"}


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _DB:
    cache = _Cache()

    def account_by_session_token(self, token):
        return REVIEWER if token == "revtoken" else None

    def is_depositor(self, token, account=None):
        return False

    def may_review(self, token, account=None):
        return token == "revtoken"

    def may_review_institution(self, token, account=None):
        return False

    def may_administer(self, token, account=None):
        return False

    def may_impersonate(self, token, account=None):
        return False

    def may_query(self, token, account=None):
        return False

    def may_review_integrity(self, token, account=None):
        return False

    def may_review_quotas(self, token, account=None):
        return False

    def datasets(self, **kwargs):
        if kwargs.get("container_uuid") == DS and kwargs.get("is_under_review"):
            return [dict(DATASET)]
        return []

    def reviews(self, **kwargs):
        return [{"assigned_to": "account:someone-else"}]


@pytest.fixture(autouse=True)
def reset():
    saved = config.enable_dataset_review
    yield
    config.enable_dataset_review = saved


def test_reviewer_page_renders_when_enabled():
    config.enable_dataset_review = True
    client = TestClient(create_app(_DB()))
    resp = client.get(
        f"/review/dataset/{DS}",
        headers={"Accept": "text/html"},
        cookies={"djehuty_session": "revtoken"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "review-reviewer.js" in resp.text
    assert "Coastal temperatures" in resp.text  # scalar value in the reviewContext blob
    assert "Title" in resp.text  # field label


def test_reviewer_page_404_when_feature_disabled():
    config.enable_dataset_review = False
    client = TestClient(create_app(_DB()))
    resp = client.get(
        f"/review/dataset/{DS}",
        headers={"Accept": "text/html"},
        cookies={"djehuty_session": "revtoken"},
    )
    assert resp.status_code == 404


def test_reviewer_page_requires_reviewer():
    config.enable_dataset_review = True
    client = TestClient(create_app(_DB()))
    resp = client.get(f"/review/dataset/{DS}", headers={"Accept": "text/html"})
    assert resp.status_code == 403
