"""
Shared fixtures for the API contract test suite (api/v2/ and api/v3/).

The tests under api/v2/ and api/v3/ exercise every public-facing /v2 and /v3
HTTP endpoint of the djehuty application and assert the observable contract:
status codes, response shapes, and persistence semantics.
"""

import os
from pathlib import Path

import pytest
from playwright.sync_api import Page

from helpers.collection import (
    create_draft_collection,
    fill_required_fields_and_publish_collection,
    get_container_uuid_from_url as get_collection_uuid_from_url,
)
from helpers.dataset import (
    create_draft_dataset,
    get_container_uuid_from_url,
)
from helpers.publish import fill_required_fields_and_publish
from pages.dataset_editor_page import DatasetEditorPage


# ---------------------------------------------------------------------------
# Auto-marker: every test under tests/api/ gets @pytest.mark.api.
# Per-version markers (@pytest.mark.api_v2 / api_v3) are added by the
# version-specific conftest.py files.
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "/api/" in str(item.fspath):
            item.add_marker(pytest.mark.api)


# ---------------------------------------------------------------------------
# Terminal summary: list AS-IS API bugs hit during the run.
#
# Bugs registered by helpers.contract.assert_status() get a dedicated block
# at the bottom of the pytest output so it stays visible in CI without
# scanning the warnings summary.
#
# When running under GitHub Actions (CI=true and GITHUB_ACTIONS=true),
# each bug also emits a ``::warning::`` workflow command so it appears as an
# inline annotation on the run page.
# ---------------------------------------------------------------------------


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    from helpers.contract import get_bug_registry, get_fixed_registry

    bugs = get_bug_registry()
    fixed = get_fixed_registry()

    if bugs:
        terminalreporter.write_sep(
            "=", "AS-IS API bugs still present", red=True, bold=True
        )
        for bug, count in sorted(bugs.items()):
            terminalreporter.write_line(f"  - {bug}  ({count}x)")
        terminalreporter.write_sep("-")
        total_unique = len(bugs)
        total_hits = sum(bugs.values())
        terminalreporter.write_line(
            f"Total: {total_unique} unique bug{'s' if total_unique != 1 else ''}, "
            f"{total_hits} hit{'s' if total_hits != 1 else ''} this run.",
            yellow=True,
            bold=True,
        )
        terminalreporter.write_sep("=", red=True)

    if fixed:
        terminalreporter.write_sep(
            "=", "AS-IS API bugs that appear FIXED (update the test)", red=True, bold=True
        )
        for bug, count in sorted(fixed.items()):
            terminalreporter.write_line(f"  - {bug}  ({count}x)")
        terminalreporter.write_sep("-")
        terminalreporter.write_line(
            "These endpoints no longer reproduce the documented AS-IS bug. "
            "If the fix is intentional, drop current_bug= and update expected= "
            "on the failing assertion so the suite records it.",
            yellow=True,
            bold=True,
        )
        terminalreporter.write_sep("=", red=True)

    # GitHub Actions inline annotations.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for bug, count in sorted(bugs.items()):
            terminalreporter.write_line(
                f"::warning title=AS-IS API bug::{bug} ({count}x)"
            )
        for bug, count in sorted(fixed.items()):
            terminalreporter.write_line(
                f"::error title=AS-IS bug appears fixed::{bug} ({count}x)"
            )


# ---------------------------------------------------------------------------
# File payload helpers
# ---------------------------------------------------------------------------

TEST_FILE_CONTENT = b"API test file content.\n"
TEST_FILE_NAME = "api-test-file.txt"


@pytest.fixture()
def test_file(tmp_path: Path) -> str:
    """Create a temporary test file and return its path."""
    file_path = tmp_path / TEST_FILE_NAME
    file_path.write_bytes(TEST_FILE_CONTENT)
    return str(file_path)


# ---------------------------------------------------------------------------
# Dataset / article fixtures (shared by v2 and v3 tests)
#
# The /v2/account/articles endpoint and the v3 dataset endpoints operate on
# the same underlying resource — these fixtures create a draft via the UI,
# yield (page, container_uuid), and tear down via the v2 DELETE endpoint
# (the only DELETE the API exposes for datasets).
# ---------------------------------------------------------------------------


@pytest.fixture()
def draft_dataset(authenticated_page: Page):
    """Create a draft dataset via the UI and yield (page, container_uuid).

    Teardown deletes via /v2/account/articles/<uuid>. Errors are ignored so
    individual tests can also delete the dataset themselves.
    """
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    yield authenticated_page, container_uuid
    authenticated_page.request.delete(f"/v2/account/articles/{container_uuid}")


@pytest.fixture()
def published_dataset(authenticated_page: Page, test_file: str):
    """Create and publish a dataset; yield (page, container_uuid)."""
    url = create_draft_dataset(authenticated_page)
    container_uuid = get_container_uuid_from_url(url)
    editor = DatasetEditorPage(authenticated_page)
    editor.wait_for_ready()
    editor.upload_file(test_file)
    editor.save()

    fill_required_fields_and_publish(
        authenticated_page,
        container_uuid,
        title="API Test Published Dataset",
        description="<p>Published dataset for API tests.</p>",
    )

    # Re-login after publish flow
    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")

    # Wait for the published dataset to become accessible
    for _ in range(5):
        resp = authenticated_page.goto(f"/datasets/{container_uuid}")
        authenticated_page.wait_for_load_state("domcontentloaded")
        if resp and resp.status == 200:
            break
        authenticated_page.wait_for_timeout(3000)

    return authenticated_page, container_uuid


# ---------------------------------------------------------------------------
# Collection fixtures (shared by v2 and v3 collection tests)
# ---------------------------------------------------------------------------


@pytest.fixture()
def draft_collection(authenticated_page: Page):
    """Create a draft collection via the UI and yield (page, container_uuid).

    Teardown deletes via /v2/account/collections/<uuid>. Errors are ignored
    so individual tests can also delete the collection themselves.
    """
    url = create_draft_collection(authenticated_page)
    container_uuid = get_collection_uuid_from_url(url)
    yield authenticated_page, container_uuid
    authenticated_page.request.delete(f"/v2/account/collections/{container_uuid}")


@pytest.fixture()
def published_collection(authenticated_page: Page):
    """Create and publish a collection; yield (page, container_uuid)."""
    url = create_draft_collection(authenticated_page)
    container_uuid = get_collection_uuid_from_url(url)
    fill_required_fields_and_publish_collection(
        authenticated_page,
        container_uuid,
        title="API Test Published Collection",
        description="<p>Published collection for API tests.</p>",
    )
    authenticated_page.goto("/login")
    authenticated_page.wait_for_url("**/my/dashboard**")
    return authenticated_page, container_uuid
