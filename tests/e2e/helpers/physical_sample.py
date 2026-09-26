"""
Physical sample helper utilities for E2E tests.
"""

import re

from playwright.sync_api import Page


def create_draft_physical_sample(page: Page) -> str:
    """Create a new draft physical sample via the UI and return its edit URL.

    Assumes the page is already authenticated as an account that may use IGSN.
    """
    page.goto("/my/physical-samples/new")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_url("**/my/physical-samples/*/edit")
    page.locator("#groups-wrapper").wait_for(state="attached")
    return page.url


def get_container_uuid_from_url(url: str) -> str:
    """Extract the container UUID from a physical sample editor URL."""
    match = re.search(r"/my/physical-samples/([^/]+)/edit", url)
    assert match, f"Cannot extract container UUID from {url}"
    return match.group(1)


def fill_required_fields_and_publish_physical_sample(
    page: Page,
    container_uuid: str,
    *,
    title: str = "E2E Test Physical Sample",
    tags: list[str] | None = None,
) -> str:
    """Publish a physical sample by calling the submit + publish APIs."""
    if tags is None:
        tags = ["e2e-test-1", "e2e-test-2", "e2e-test-3", "e2e-test-4"]

    page.goto(f"/my/physical-samples/{container_uuid}/edit")
    page.wait_for_load_state("domcontentloaded")
    page.locator("#groups-wrapper").wait_for(state="attached")

    group_id = page.evaluate(
        "() => { let g = document.querySelector(\"input[name='groups']\"); "
        "return g ? g.value : null; }"
    )
    category_uuid = page.evaluate(
        "() => { let c = document.querySelector(\"input[name='categories']\"); "
        "return c ? c.value : null; }"
    )

    tag_response = page.request.post(
        f"/v3/physical-samples/{container_uuid}/tags",
        data={"tags": tags},
    )
    assert tag_response.ok, (
        f"Add tag failed: {tag_response.status} {tag_response.text()} "
        f"url={tag_response.url} server={tag_response.headers.get('server')}"
    )

    form_data = {
        "title": title,
        "abstract": "<p>Physical sample for E2E tests.</p>",
        "publisher": "4TU.ResearchData",
        "organizations": "E2E Organisation",
        "physical_storage_location": "E2E storage room",
        "sample_owner_name": "E2E Owner",
        "sample_owner_email": "e2e-owner@example.com",
        "group_id": int(group_id) if group_id else None,
        "agreed_to_publish": True,
        "categories": [category_uuid] if category_uuid else [],
    }
    response = page.request.put(
        f"/v3/physical-samples/{container_uuid}/submit-for-review",
        data=form_data,
    )
    assert response.ok, f"Submit failed: {response.status} {response.text()}"

    # Sets the impersonator cookie the publish endpoint reads.
    page.goto(f"/review/goto-physical-sample/{container_uuid}")
    page.wait_for_load_state("domcontentloaded")

    response = page.request.post(f"/v3/physical-samples/{container_uuid}/publish")
    assert response.ok, f"Publish failed: {response.status} {response.text()}"

    return container_uuid
