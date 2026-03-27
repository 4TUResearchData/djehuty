"""
Collection helper utilities for E2E tests.
"""

import re

from playwright.sync_api import Page


def create_draft_collection(page: Page) -> str:
    """Create a new draft collection via the UI and return its edit URL.

    Assumes the page is already authenticated.
    """
    page.goto("/my/collections/new")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_url("**/my/collections/*/edit", timeout=60000)
    page.locator(".collection-content").wait_for(state="visible")
    return page.url


def get_container_uuid_from_url(url: str) -> str:
    """Extract the container UUID from a collection editor URL."""
    match = re.search(r"/my/collections/([^/]+)/edit", url)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot extract container UUID from: {url}")


def delete_collection(page: Page, collection_url: str):
    """Delete a collection identified by its editor URL."""
    page.goto(collection_url)
    page.wait_for_load_state("domcontentloaded")
    page.locator(".collection-content-loader").wait_for(state="hidden")
    page.locator(".collection-content").wait_for(state="visible")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#delete").click()
    page.wait_for_url("**/my/collections", wait_until="domcontentloaded")


def fill_required_fields_and_publish_collection(
    page: Page,
    container_uuid: str,
    *,
    title: str = "E2E Test Collection",
    description: str = "<p>Test collection for E2E tests.</p>",
):
    """Publish a collection by filling required fields via API, then publishing.

    Adds tags, an author, and a category via the API, then saves and publishes
    through the UI. Returns the container_uuid.
    """
    page.goto(f"/my/collections/{container_uuid}/edit")
    page.wait_for_load_state("domcontentloaded")
    page.locator(".collection-content").wait_for(state="visible")

    # Get a group_id from the editor page
    group_id = page.evaluate(
        "() => { let g = document.querySelector(\"input[name='groups']\"); "
        "return g ? g.value : null; }"
    )

    # Get a category from the editor page
    category_uuid = page.evaluate(
        "() => { let c = document.querySelector(\"input[name='categories']\"); "
        "return c ? c.value : null; }"
    )

    # Add tags via API
    page.request.post(
        f"/v3/collections/{container_uuid}/tags",
        data={"tags": ["e2e-test", "collection-test", "automated", "playwright"]},
    )

    # Add an author via API
    page.request.post(
        f"/v2/account/collections/{container_uuid}/authors",
        data={"authors": [{"first_name": "Test", "last_name": "Author"}]},
    )

    # Add a category via API
    if category_uuid:
        page.request.post(
            f"/v2/account/collections/{container_uuid}/categories",
            data={"categories": [category_uuid]},
        )

    # Save via API with required fields
    form_data = {
        "title": title,
        "description": description,
        "group_id": int(group_id) if group_id else None,
        "publisher": "4TU.ResearchData",
        "language": "en",
        "categories": [category_uuid] if category_uuid else [],
    }
    response = page.request.put(
        f"/v2/account/collections/{container_uuid}",
        data=form_data,
    )
    assert response.ok, f"Save failed: {response.status} {response.text()}"

    # Publish via API
    response = page.request.post(
        f"/v3/collections/{container_uuid}/publish",
    )
    assert response.ok, f"Publish failed: {response.status} {response.text()}"

    return container_uuid
