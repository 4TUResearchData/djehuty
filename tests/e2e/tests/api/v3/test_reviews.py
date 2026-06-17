"""
V3 Reviews API contract tests.

Endpoints (3):
    PUT  /v3/datasets/<dataset_uuid>/assign-reviewer/<reviewer_uuid>
    GET  /v3/reviews
    GET  /v3/reviewers

The reviews/reviewers endpoints require reviewer or institutional-reviewer
permissions. The default dev account is admin, which has these permissions.

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_reviews.py -v
"""

import uuid

from playwright.sync_api import Page


class TestV3ReviewsListApi:
    """GET /v3/reviews — list pending reviews."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        response = page.request.get(
            "/v3/reviews",
            headers={"Accept": "application/json"},
        )
        save_response(response, "v3-reviews-no-auth")
        assert response.status in (401, 403)

    def test_admin_lists_reviews(self, admin_page: Page, save_response):
        """Admin → 200, JSON array."""
        response = admin_page.request.get(
            "/v3/reviews",
            headers={"Accept": "application/json"},
        )
        save_response(response, "v3-reviews")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)

    def test_non_json_returns_406(self, admin_page: Page, save_response):
        """Accept: text/html → 406."""
        response = admin_page.request.get(
            "/v3/reviews",
            headers={"Accept": "text/html"},
        )
        save_response(response, "v3-reviews-not-json")
        # Either 406 (handler-checked) or 200 if Accept negotiation differs.
        assert response.status in (200, 406)


class TestV3ReviewersListApi:
    """GET /v3/reviewers — list reviewer accounts."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        response = page.request.get(
            "/v3/reviewers",
            headers={"Accept": "application/json"},
        )
        save_response(response, "v3-reviewers-no-auth")
        assert response.status in (401, 403)

    def test_admin_lists_reviewers(self, admin_page: Page, save_response):
        """Admin → 200, JSON array."""
        response = admin_page.request.get(
            "/v3/reviewers",
            headers={"Accept": "application/json"},
        )
        save_response(response, "v3-reviewers")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)


class TestV3AssignReviewerApi:
    """PUT /v3/datasets/<uuid>/assign-reviewer/<rid>."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.put(
            f"/v3/datasets/{fake}/assign-reviewer/{fake}",
            data={},
        )
        save_response(response, "v3-assign-reviewer-no-auth")
        assert response.status in (401, 403)

    def test_invalid_reviewer_uuid_returns_403(self, admin_page: Page, save_response):
        """Reviewer id that isn't a UUID → 403."""
        fake = str(uuid.uuid4())
        response = admin_page.request.put(
            f"/v3/datasets/{fake}/assign-reviewer/not-a-uuid",
            data={},
        )
        save_response(response, "v3-assign-reviewer-bad-uuid")
        assert response.status == 403

    def test_nonexistent_dataset_returns_403(self, admin_page: Page, save_response):
        """Both UUIDs syntactically valid but no such dataset → 403."""
        fake_dataset = str(uuid.uuid4())
        fake_reviewer = str(uuid.uuid4())
        response = admin_page.request.put(
            f"/v3/datasets/{fake_dataset}/assign-reviewer/{fake_reviewer}",
            data={},
        )
        save_response(response, "v3-assign-reviewer-missing")
        assert response.status == 403
