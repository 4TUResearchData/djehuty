"""Unit tests for PUT /v3/profile.

The self-service profile update must not let a user assign privileged account
fields. ``email`` in particular drives privilege resolution (roles are keyed by
e-mail), so forwarding it would allow escalation to an administrator.
"""

import pytest
from fastapi.testclient import TestClient

from djehuty.application import create_app

AUTH = {"Authorization": "tok"}

PRIVILEGED_FIELDS = (
    "email",
    "active",
    "institution_id",
    "institution_user_id",
    "maximum_file_size",
)


class _Cache:
    def invalidate_by_prefix(self, prefix):
        pass


class _Db:
    def __init__(self):
        self.cache = _Cache()
        self.update_kwargs = None

    def account_by_session_token(self, token):
        return {"uuid": "caller-1", "email": "caller@example.org"} if token == "tok" else None

    def update_account(self, account_uuid, **kwargs):
        self.update_kwargs = kwargs
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _client():
    db = _Db()
    return TestClient(create_app(db)), db


@pytest.mark.parametrize("field", PRIVILEGED_FIELDS)
def test_profile_update_rejects_privileged_fields(field):
    client, db = _client()
    response = client.put("/v3/profile", json={field: 1, "first_name": "Ada"}, headers=AUTH)
    assert response.status_code == 400
    assert db.update_kwargs is None


def test_profile_update_applies_normal_fields():
    client, db = _client()
    response = client.put(
        "/v3/profile", json={"first_name": "Ada", "job_title": "Steward"}, headers=AUTH
    )
    assert response.status_code == 204
    assert db.update_kwargs["first_name"] == "Ada"
    assert db.update_kwargs["job_title"] == "Steward"
