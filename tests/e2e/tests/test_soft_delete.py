"""
Soft-delete lifecycle tests for draft datasets.

Covers:
    - Deleting a draft moves it out of Drafts and into the Deleted list
      (it is soft-deleted, not purged).
    - Restoring a soft-deleted draft returns it to Drafts.
    - Permanent deletion is title-gated and removes the draft for good.

Run with:
    cd tests/e2e && python -m pytest tests/test_soft_delete.py -v
"""

import uuid

import pytest
from playwright.sync_api import Page, expect

from config import BASE_URL
from helpers.dataset import create_draft_dataset, get_container_uuid_from_url
from pages.dataset_editor_page import DatasetEditorPage


def _named_draft(page: Page) -> tuple[str, str, str]:
    """Create a draft with a unique title. Returns (edit_url, container_uuid, title)."""
    url = create_draft_dataset(page)
    editor = DatasetEditorPage(page)
    title = f"SoftDelete-{uuid.uuid4().hex[:8]}"
    editor.set_title(title)
    editor.save()
    return url, get_container_uuid_from_url(url), title


@pytest.mark.dataset
class TestSoftDelete:
    def test_deleted_draft_moves_to_deleted_list(self, authenticated_page: Page, screenshot):
        """A deleted draft leaves Drafts and appears under Deleted."""
        url, _container, title = _named_draft(authenticated_page)

        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()

        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        screenshot(authenticated_page, "after-soft-delete")

        expect(authenticated_page.locator("#table-deleted")).to_contain_text(title)
        drafts_table = authenticated_page.locator("#table-unpublished")
        if drafts_table.count() > 0:
            expect(drafts_table).not_to_contain_text(title)

    def test_restore_returns_draft_to_drafts(self, authenticated_page: Page, screenshot):
        """Restoring a soft-deleted draft puts it back in Drafts."""
        url, container, title = _named_draft(authenticated_page)

        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()

        # Restore via the endpoint the Deleted-list button targets.
        authenticated_page.goto(f"/my/datasets/{container}/restore")
        authenticated_page.wait_for_url("**/my/datasets", wait_until="domcontentloaded")
        screenshot(authenticated_page, "after-restore")

        expect(authenticated_page.locator("#table-unpublished")).to_contain_text(title)
        deleted_table = authenticated_page.locator("#table-deleted")
        if deleted_table.count() > 0:
            expect(deleted_table).not_to_contain_text(title)

    def test_permanent_delete_requires_confirmation(self, authenticated_page: Page, screenshot):
        """Without ticking the box nothing is deleted; ticking it purges the draft."""
        url, container, title = _named_draft(authenticated_page)

        authenticated_page.goto(url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        DatasetEditorPage(authenticated_page).delete()

        # Submitting without ticking the box keeps the record.
        authenticated_page.goto(f"/my/datasets/{container}/delete-permanently")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.get_by_role("button", name="Delete permanently").click()
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.goto("/my/datasets")
        authenticated_page.wait_for_load_state("domcontentloaded")
        expect(authenticated_page.locator("#table-deleted")).to_contain_text(title)

        # Ticking the box purges it.
        authenticated_page.goto(f"/my/datasets/{container}/delete-permanently")
        authenticated_page.wait_for_load_state("domcontentloaded")
        authenticated_page.locator("#confirm").check()
        authenticated_page.get_by_role("button", name="Delete permanently").click()
        authenticated_page.wait_for_url("**/my/datasets", wait_until="domcontentloaded")
        screenshot(authenticated_page, "after-permanent-delete")

        expect(authenticated_page.locator("body")).not_to_contain_text(title)


@pytest.mark.dataset
class TestSoftDeleteAccessControl:
    def test_restore_unknown_dataset_is_forbidden(self, authenticated_page: Page):
        """Restoring a dataset the account does not own returns 403."""
        response = authenticated_page.goto(f"/my/datasets/{uuid.uuid4()}/restore")
        assert response is not None
        assert response.status == 403
