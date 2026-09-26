"""V3 Physical samples (IGSN) API contract tests.

Endpoints (17):
    GET,PUT    /v3/physical-samples[/<container_uuid>]
    GET,POST   /v3/physical-samples/<uuid>/creators
    GET,DELETE /v3/physical-samples/<uuid>/creators/<creator_uuid>
    POST       /v3/physical-samples/<uuid>/reorder-creators
    GET,POST   /v3/physical-samples/<uuid>/dates
    DELETE     /v3/physical-samples/<uuid>/dates/<date_uuid>
    GET,POST   /v3/physical-samples/<uuid>/related-resources
    DELETE     /v3/physical-samples/<uuid>/related-resources/<resource_uuid>
    GET,POST,DELETE /v3/physical-samples/<uuid>/tags
    GET,POST,PUT    /v3/physical-samples/<uuid>/categories
    GET,POST   /v3/physical-samples/<uuid>/private_links
    GET,PUT,DELETE  /v3/physical-samples/<uuid>/private_links/<link_id>
    PUT        /v3/physical-samples/<uuid>/submit-for-review
    POST       /v3/physical-samples/<uuid>/publish
    POST       /v3/physical-samples/<uuid>/decline
    PUT        /v3/physical-samples/<uuid>/assign-reviewer/<reviewer_uuid>

These pin the AS-IS behaviour so flipping the api-v3 route group new<->legacy is
invisible to clients.

PREREQUISITE: the stack must have IGSN enabled (an <igsn> config block, so
config.supports_igsn and config.igsn_enabled are true, with an allow-list that
admits the test account) and the physical-sample schema migration applied.
Without it, PUT /v3/physical-samples is 403 and the draft fixture fails.

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_physical_samples.py -v
"""

import uuid

import pytest
from playwright.sync_api import Page


def _container_uuid_from_location(response) -> str:
    """Extract the container UUID from a {"location": ".../<uuid>"} body."""
    location = response.json()["location"]
    return location.rstrip("/").split("/")[-1]


@pytest.fixture()
def draft_physical_sample(authenticated_page: Page):
    """Create a draft physical sample via the API and yield (page, container_uuid).

    Teardown removes it via the UI delete route (the v3 API exposes no sample
    DELETE); errors are ignored so a test may also delete it itself.
    """
    response = authenticated_page.request.put("/v3/physical-samples", data={})
    if response.status == 403:
        pytest.skip(
            "IGSN is not enabled on this stack (PUT /v3/physical-samples -> 403); "
            "enable the <igsn> config block to run the physical-sample API tests."
        )
    assert response.status == 201, f"Draft create returned {response.status}, expected 201."
    container_uuid = _container_uuid_from_location(response)
    yield authenticated_page, container_uuid
    authenticated_page.request.get(f"/my/physical-samples/{container_uuid}/delete")


class TestV3PhysicalSampleDetails:
    """GET/PUT /v3/physical-samples[/<uuid>]."""

    def test_create_requires_auth(self, page: Page, save_response):
        response = page.request.put("/v3/physical-samples", data={})
        save_response(response, "v3-ps-create-no-auth")
        assert response.status == 403

    def test_create_and_read_draft(self, draft_physical_sample, save_response):
        page, container_uuid = draft_physical_sample
        response = page.request.get(f"/v3/physical-samples/{container_uuid}")
        save_response(response, "v3-ps-read-draft")
        assert response.status == 200
        body = response.json()
        assert body["uuid"] is not None
        # format_physical_sample_record shape.
        for key in ("title", "abstract", "methods", "resource_type", "subject", "last_modified"):
            assert key in body

    def test_update_draft(self, draft_physical_sample, save_response):
        page, container_uuid = draft_physical_sample
        response = page.request.put(
            f"/v3/physical-samples/{container_uuid}",
            data={"title": "Updated basalt core"},
        )
        save_response(response, "v3-ps-update-draft")
        assert response.status == 204

    def test_read_missing_returns_404(self, authenticated_page: Page, save_response):
        response = authenticated_page.request.get(f"/v3/physical-samples/{uuid.uuid4()}")
        save_response(response, "v3-ps-read-404")
        assert response.status == 404


class TestV3PhysicalSampleCreators:
    """Creators sub-resource."""

    def test_list_requires_auth(self, page: Page, save_response):
        """AS-IS: an unauthenticated list is 403 'Not allowed.'."""
        response = page.request.get(f"/v3/physical-samples/{uuid.uuid4()}/creators")
        save_response(response, "v3-ps-creators-no-auth")
        assert response.status == 403

    def test_list_creators(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        response = page.request.get(f"/v3/physical-samples/{container_uuid}/creators")
        assert response.status == 200
        assert isinstance(response.json(), list)

    def test_add_creators_by_object(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        response = page.request.post(
            f"/v3/physical-samples/{container_uuid}/creators",
            data={
                "authors": [{"name": "Ada Lovelace", "first_name": "Ada", "last_name": "Lovelace"}]
            },
        )
        assert response.status == 204
        listed = page.request.get(f"/v3/physical-samples/{container_uuid}/creators").json()
        assert any(c.get("full_name") == "Ada Lovelace" for c in listed)

    def test_add_creators_expects_list_or_object(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        response = page.request.post(
            f"/v3/physical-samples/{container_uuid}/creators", data="not-a-list"
        )
        assert response.status == 400

    def test_get_creator_bad_uuid_is_404(self, authenticated_page: Page):
        response = authenticated_page.request.get(
            f"/v3/physical-samples/{uuid.uuid4()}/creators/not-a-uuid"
        )
        assert response.status == 404


class TestV3PhysicalSampleDates:
    """Dates sub-resource."""

    def test_list_requires_auth(self, page: Page):
        response = page.request.get(f"/v3/physical-samples/{uuid.uuid4()}/dates")
        assert response.status == 403

    def test_add_and_delete_date(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        added = page.request.post(
            f"/v3/physical-samples/{container_uuid}/dates",
            data=[{"type": "collected", "date": "2010-11-02"}],
        )
        assert added.status == 204
        dates = page.request.get(f"/v3/physical-samples/{container_uuid}/dates").json()
        assert dates
        date_uuid = dates[0]["uuid"]
        removed = page.request.delete(f"/v3/physical-samples/{container_uuid}/dates/{date_uuid}")
        assert removed.status == 204

    def test_add_dates_expects_list(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        response = page.request.post(
            f"/v3/physical-samples/{container_uuid}/dates", data={"type": "collected"}
        )
        assert response.status == 400

    def test_delete_absent_date_is_500(self, draft_physical_sample):
        """AS-IS: deleting an absent date on a valid draft is 500, not 404."""
        page, container_uuid = draft_physical_sample
        response = page.request.delete(
            f"/v3/physical-samples/{container_uuid}/dates/{uuid.uuid4()}"
        )
        assert response.status == 500


class TestV3PhysicalSampleRelatedResources:
    """Related-resources sub-resource."""

    def test_list_requires_auth(self, page: Page):
        response = page.request.get(f"/v3/physical-samples/{uuid.uuid4()}/related-resources")
        assert response.status == 403

    def test_add_related_resource(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        response = page.request.post(
            f"/v3/physical-samples/{container_uuid}/related-resources",
            data=[
                {
                    "identifier": "10.4121/related",
                    "identifier-type": "IGSNDOI",
                    "relation-type": "IsDerivedFrom",
                }
            ],
        )
        assert response.status == 204


class TestV3PhysicalSampleTags:
    """Tags sub-resource."""

    def test_add_and_list_tags(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        added = page.request.post(
            f"/v3/physical-samples/{container_uuid}/tags",
            data={"tags": ["basalt", "core sample"]},
        )
        assert added.status == 205
        listed = page.request.get(f"/v3/physical-samples/{container_uuid}/tags").json()
        assert "basalt" in listed

    def test_add_tags_missing_field_is_400(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        response = page.request.post(
            f"/v3/physical-samples/{container_uuid}/tags", data={"nope": []}
        )
        assert response.status == 400


class TestV3PhysicalSampleCategories:
    """Categories sub-resource."""

    def test_missing_categories_field_is_400(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        response = page.request.post(
            f"/v3/physical-samples/{container_uuid}/categories", data={"nope": []}
        )
        assert response.status == 400


class TestV3PhysicalSamplePrivateLinks:
    """Private-links sub-resource."""

    def test_create_returns_200(self, draft_physical_sample):
        """AS-IS: private-link creation returns 200 (not 201) with the location."""
        page, container_uuid = draft_physical_sample
        response = page.request.post(
            f"/v3/physical-samples/{container_uuid}/private_links", data={}
        )
        assert response.status == 200
        assert "location" in response.json()

    def test_list_missing_sample_is_404(self, authenticated_page: Page):
        response = authenticated_page.request.get(
            f"/v3/physical-samples/{uuid.uuid4()}/private_links"
        )
        assert response.status == 404


class TestV3PhysicalSamplePublishing:
    """Submit / publish / decline / assign-reviewer."""

    def test_publish_requires_reviewer(self, draft_physical_sample):
        """A depositor without reviewer rights cannot publish -> 403."""
        page, container_uuid = draft_physical_sample
        response = page.request.post(f"/v3/physical-samples/{container_uuid}/publish", data={})
        assert response.status == 403

    def test_decline_requires_reviewer(self, draft_physical_sample):
        page, container_uuid = draft_physical_sample
        response = page.request.post(f"/v3/physical-samples/{container_uuid}/decline", data={})
        assert response.status == 403

    def test_assign_reviewer_bad_reviewer_uuid_is_400(self, authenticated_page: Page):
        response = authenticated_page.request.put(
            f"/v3/physical-samples/{uuid.uuid4()}/assign-reviewer/not-a-uuid"
        )
        assert response.status == 400

    def test_submit_requires_auth(self, page: Page):
        response = page.request.put(
            f"/v3/physical-samples/{uuid.uuid4()}/submit-for-review", data={}
        )
        assert response.status == 403
