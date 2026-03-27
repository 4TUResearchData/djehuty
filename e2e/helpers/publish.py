"""
Helpers for publishing datasets via API calls in E2E tests.
"""

import re
from datetime import date, timedelta

from playwright.sync_api import Page


def fill_required_fields_and_publish(
    page: Page,
    container_uuid: str,
    *,
    title: str = "E2E Test Dataset",
    description: str = "<p>Test dataset for E2E tests.</p>",
    is_embargoed: bool = False,
    embargo_until_date: str | None = None,
    embargo_type: str = "file",
    embargo_reason: str = "<p>Under review.</p>",
    is_restricted: bool = False,
    restricted_reason: str = "<p>Restricted data.</p>",
    eula: str = "<p>Test EULA.</p>",
):
    """Publish a dataset by calling the submit + publish APIs.

    Assumes the page is authenticated as the admin/dev account.
    Navigates to the dataset editor to extract group/category values,
    then submits for review and publishes via the review flow.

    Returns the container_uuid for constructing the public URL.
    """
    # Navigate to editor to extract required values
    page.goto(f"/my/datasets/{container_uuid}/edit")
    page.wait_for_load_state("domcontentloaded")
    page.locator(".article-content").wait_for(state="visible")

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

    # Get the first available license
    license_id = page.evaluate(
        "() => { let opt = document.querySelector('#license_open option:not([disabled])'); "
        "return opt ? opt.value : '2'; }"
    )

    # Extract dataset UUID from the private links button
    href = page.locator("#private-links").get_attribute("href")
    match = re.search(r"/my/datasets/([^/]+)/private_links", href)
    dataset_uuid = match.group(1) if match else None

    # Set required metadata (tags, authors, categories) via the v2 dataset
    # update endpoint.  This single PUT writes tags directly into the database,
    # avoiding the timing issues that can occur with separate v3 tag POSTs.
    update_data = {
        "tags": ["e2e-test"],
        "authors": [{"first_name": "Test", "last_name": "Author"}],
        "title": title,
        "description": description,
        "defined_type": "dataset",
    }
    if category_uuid:
        update_data["categories"] = [category_uuid]

    update_response = page.request.put(
        f"/v2/account/articles/{container_uuid}",
        data=update_data,
    )
    assert update_response.ok, (
        f"Dataset update failed: {update_response.status} {update_response.text()}"
    )

    # Build the form data for submit-for-review
    form_data = {
        "title": title,
        "description": description,
        "defined_type": "dataset",
        "is_embargoed": is_embargoed or is_restricted,
        "is_metadata_record": False,
        "agreed_to_deposit_agreement": True,
        "agreed_to_publish": True,
        "categories": [category_uuid] if category_uuid else [],
        "group_id": int(group_id) if group_id else None,
        "license_id": int(license_id) if license_id else 2,
        "publisher": "4TU.ResearchData",
        "language": "en",
    }

    if is_embargoed and not is_restricted:
        if not embargo_until_date:
            future = date.today() + timedelta(days=365)
            embargo_until_date = future.isoformat()
        form_data["embargo_until_date"] = embargo_until_date
        form_data["embargo_type"] = embargo_type
        form_data["embargo_title"] = "Under embargo"
        form_data["embargo_reason"] = embargo_reason
    elif is_restricted:
        form_data["embargo_options"] = [{"id": 1000, "type": "restricted_access"}]
        form_data["embargo_title"] = "Restricted access"
        form_data["embargo_reason"] = restricted_reason
        form_data["eula"] = eula
        form_data["license_id"] = 149

    # Submit for review
    response = page.request.put(
        f"/v3/datasets/{container_uuid}/submit-for-review",
        data=form_data,
    )
    assert response.ok, f"Submit failed: {response.status} {response.text()}"

    # Navigate to review page to set up impersonation cookies
    # This sets the impersonator cookie needed by the publish endpoint
    page.goto(f"/review/goto-dataset/{dataset_uuid}")
    page.wait_for_load_state("domcontentloaded")

    # Publish via API (now with impersonator cookie set)
    response = page.request.post(
        f"/v3/datasets/{container_uuid}/publish",
    )
    assert response.ok, f"Publish failed: {response.status} {response.text()}"

    return container_uuid


def create_private_link(page: Page, container_uuid: str, days: int = 7) -> str:
    """Create a private link via the API and return the link ID.

    Args:
        page: An authenticated page.
        container_uuid: The dataset container UUID.
        days: Number of days until the link expires.

    Returns:
        The private link ID string.
    """
    expires_date = (date.today() + timedelta(days=days)).isoformat()
    response = page.request.post(
        f"/v2/account/articles/{container_uuid}/private_links",
        data={"expires_date": expires_date},
    )
    assert response.ok, f"Create private link failed: {response.status} {response.text()}"
    link_data = response.json()
    # The response "location" is like "/private_datasets/<id>"
    return link_data["location"].rstrip("/").split("/")[-1]
