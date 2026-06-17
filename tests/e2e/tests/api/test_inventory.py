"""
Master inventory of every public-facing /v2/ and /v3/ API endpoint.

This file is the checklist for API coverage. It holds a hand-curated list of
every (path, handler) pair registered in src/djehuty/web/wsgi.py and verifies
the list stays in sync with the source via static parsing — adding or
removing a route in wsgi.py without updating this file fails the drift test.

The per-resource files (test_articles.py, test_collections.py, ...) carry
the actual behavioural assertions.

Note on runtime route-existence checks
--------------------------------------
djehuty returns the same JSON body (``{"message": "This resource does not
exist."}``) for both a routing miss and a handler-emitted 404 — see
``error_404`` in src/djehuty/web/wsgi.py. So a live response cannot
distinguish "URL not routed" from "handler 404". The drift tests below
parse wsgi.py at the source level instead.
"""

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Endpoint inventory — keep in sync with src/djehuty/web/wsgi.py URL map.
# (version, path_template, handler_name)
# ---------------------------------------------------------------------------

V2_ENDPOINTS = [
    # OAuth / token
    ("/v2/account/applications/authorize", "api_authorize"),
    ("/v2/token", "api_token"),
    # Institution (private)
    ("/v2/account/institution", "api_private_institution"),
    ("/v2/account/institution/users/<account_id>", "api_private_institution_account"),
    ("/v2/account/institution/accounts", "api_private_institution_accounts"),
    # Articles (public)
    ("/v2/articles", "api_datasets"),
    ("/v2/articles/search", "api_datasets_search"),
    ("/v2/articles/<dataset_id>", "api_dataset_details"),
    ("/v2/articles/<dataset_id>/versions", "api_dataset_versions"),
    ("/v2/articles/<dataset_id>/versions/<version>", "api_dataset_version_details"),
    (
        "/v2/articles/<dataset_id>/versions/<version>/embargo",
        "api_dataset_version_embargo",
    ),
    (
        "/v2/articles/<dataset_id>/versions/<version>/confidentiality",
        "api_dataset_version_confidentiality",
    ),
    (
        "/v2/articles/<dataset_id>/versions/<version>/update_thumb",
        "api_dataset_version_update_thumb",
    ),
    ("/v2/articles/<dataset_id>/files", "api_dataset_files"),
    ("/v2/articles/<dataset_id>/files/<file_id>", "api_dataset_file_details"),
    # Articles (private)
    ("/v2/account/articles", "api_private_datasets"),
    ("/v2/account/articles/search", "api_private_datasets_search"),
    ("/v2/account/articles/<dataset_id>", "api_private_dataset_details"),
    ("/v2/account/articles/<dataset_id>/authors", "api_private_dataset_authors"),
    (
        "/v2/account/articles/<dataset_id>/authors/<author_id>",
        "api_private_dataset_author_delete",
    ),
    ("/v2/account/articles/<dataset_id>/funding", "api_private_dataset_funding"),
    (
        "/v2/account/articles/<dataset_id>/funding/<funding_id>",
        "api_private_dataset_funding_delete",
    ),
    ("/v2/account/articles/<dataset_id>/categories", "api_private_dataset_categories"),
    (
        "/v2/account/articles/<dataset_id>/categories/<category_id>",
        "api_private_delete_dataset_category",
    ),
    ("/v2/account/articles/<dataset_id>/embargo", "api_private_dataset_embargo"),
    ("/v2/account/articles/<dataset_id>/files", "api_private_dataset_files"),
    (
        "/v2/account/articles/<dataset_id>/files/<file_id>",
        "api_private_dataset_file_details",
    ),
    (
        "/v2/account/articles/<dataset_id>/private_links",
        "api_private_dataset_private_links",
    ),
    (
        "/v2/account/articles/<dataset_id>/private_links/<link_id>",
        "api_private_dataset_private_links_details",
    ),
    (
        "/v2/account/articles/<dataset_id>/reserve_doi",
        "api_private_dataset_reserve_doi",
    ),
    ("/v2/account/articles/<dataset_id>/publish", "api_v3_dataset_publish"),
    # Collections (public)
    ("/v2/collections", "api_collections"),
    ("/v2/collections/search", "api_collections_search"),
    ("/v2/collections/<collection_id>", "api_collection_details"),
    ("/v2/collections/<collection_id>/versions", "api_collection_versions"),
    (
        "/v2/collections/<collection_id>/versions/<version>",
        "api_collection_version_details",
    ),
    ("/v2/collections/<collection_id>/articles", "api_collection_datasets"),
    # Collections (private)
    ("/v2/account/collections", "api_private_collections"),
    ("/v2/account/collections/search", "api_private_collections_search"),
    ("/v2/account/collections/<collection_id>", "api_private_collection_details"),
    (
        "/v2/account/collections/<collection_id>/authors",
        "api_private_collection_authors",
    ),
    (
        "/v2/account/collections/<collection_id>/authors/<author_id>",
        "api_private_collection_author_delete",
    ),
    (
        "/v2/account/collections/<collection_id>/categories",
        "api_private_collection_categories",
    ),
    (
        "/v2/account/collections/<collection_id>/categories/<category_id>",
        "api_private_delete_collection_category",
    ),
    (
        "/v2/account/collections/<collection_id>/articles",
        "api_private_collection_datasets",
    ),
    (
        "/v2/account/collections/<collection_id>/articles/<dataset_id>",
        "api_private_collection_dataset_delete",
    ),
    (
        "/v2/account/collections/<collection_id>/reserve_doi",
        "api_private_collection_reserve_doi",
    ),
    (
        "/v2/account/collections/<collection_id>/funding",
        "api_private_collection_funding",
    ),
    (
        "/v2/account/collections/<collection_id>/funding/<funding_id>",
        "api_private_collection_funding_delete",
    ),
    # Authors / funding (private)
    ("/v2/account/authors/search", "api_private_authors_search"),
    ("/v2/account/authors/<author_id>", "api_private_author_details"),
    ("/v2/account/funding/search", "api_private_funding_search"),
    # Misc
    ("/v2/licenses", "api_licenses"),
    ("/v2/categories", "api_categories"),
    ("/v2/account", "api_account"),
]

V3_ENDPOINTS = [
    # Datasets — list / search / top / timeline
    ("/v3/datasets", "api_v3_datasets"),
    ("/v3/codemeta", "api_v3_codemeta"),
    ("/v3/datasets/search", "api_v3_datasets_search"),
    ("/v3/datasets/top/<item_type>", "api_v3_datasets_top"),
    ("/v3/datasets/timeline/<item_type>", "api_v3_datasets_timeline"),
    # Datasets — review workflow
    ("/v3/datasets/<dataset_id>/submit-for-review", "api_v3_dataset_submit"),
    ("/v3/datasets/<dataset_id>/publish", "api_v3_dataset_publish"),
    ("/v3/datasets/<dataset_id>/decline", "api_v3_dataset_decline"),
    # Datasets — content management
    ("/v3/datasets/<container_uuid>/repair_md5s", "api_v3_repair_md5s"),
    ("/v3/datasets/<dataset_id>/doi-badge-v<version>.svg", "api_v3_doi_badge"),
    ("/v3/datasets/<dataset_id>/doi-badge.svg", "api_v3_doi_badge"),
    ("/v3/datasets/<dataset_id>/upload", "api_v3_dataset_upload_file"),
    ("/v3/datasets/<dataset_id>/image-files", "api_v3_dataset_image_files"),
    ("/v3/datasets/<dataset_id>/update-thumbnail", "api_v3_datasets_update_thumbnail"),
    ("/v3/file/<file_id>", "api_v3_file"),
    # Datasets — git deposits (REST, not git-protocol)
    ("/v3/datasets/<dataset_id>.git/files", "api_v3_dataset_git_files"),
    ("/v3/datasets/<dataset_id>.git/branches", "api_v3_dataset_git_branches"),
    (
        "/v3/datasets/<dataset_id>.git/set-default-branch",
        "api_v3_datasets_git_set_default_branch",
    ),
    # Datasets — authors / references / tags
    ("/v3/datasets/<container_uuid>/authors", "api_v3_dataset_authors"),
    ("/v3/datasets/<container_uuid>/authors/<author_uuid>", "api_v3_dataset_authors"),
    (
        "/v3/datasets/<container_uuid>/reorder-authors",
        "api_v3_datasets_authors_reorder",
    ),
    ("/v3/datasets/<dataset_id>/references", "api_v3_dataset_references"),
    ("/v3/datasets/<dataset_id>/tags", "api_v3_dataset_tags"),
    # Datasets — collaborators
    ("/v3/datasets/<dataset_uuid>/collaborators", "api_v3_dataset_collaborators"),
    (
        "/v3/datasets/<dataset_uuid>/collaborators/<collaborator_uuid>",
        "api_v3_update_collaborators",
    ),
    # Collections (v3)
    ("/v3/collections/<collection_id>/publish", "api_v3_collection_publish"),
    (
        "/v3/collections/<container_uuid>/reorder-authors",
        "api_v3_collections_authors_reorder",
    ),
    ("/v3/collections/<collection_id>/references", "api_v3_collection_references"),
    ("/v3/collections/<collection_id>/tags", "api_v3_collection_tags"),
    # Profile
    ("/v3/profile", "api_v3_profile"),
    ("/v3/profile/categories", "api_v3_profile_categories"),
    ("/v3/profile/quota-request", "api_v3_profile_quota_request"),
    ("/v3/profile/picture", "api_v3_profile_picture"),
    ("/v3/profile/picture/<account_uuid>", "api_v3_profile_picture_for_account"),
    # Search / accounts / authors
    ("/v3/groups", "api_v3_groups"),
    ("/v3/tags/search", "api_v3_tags_search"),
    ("/v3/accounts/search", "api_v3_accounts_search"),
    ("/v3/authors/<author_uuid>", "api_v3_author_details"),
    # RO-Crate
    ("/v3/ro-crates", "api_v3_ro_crates"),
    (
        "/v3/datasets/<container_uuid>/ro-crate-metadata.json",
        "api_v3_datasets_ro_crate",
    ),
    (
        "/v3/datasets/<container_uuid>/versions/<version>/ro-crate-metadata.json",
        "api_v3_datasets_ro_crate",
    ),
    # Explore (SPARQL)
    ("/v3/explore/types", "api_v3_explore_types"),
    ("/v3/explore/properties", "api_v3_explore_properties"),
    ("/v3/explore/property_value_types", "api_v3_explore_property_types"),
    ("/v3/explore/clear-cache", "api_v3_explore_clear_cache"),
    # Reviews
    (
        "/v3/datasets/<dataset_uuid>/assign-reviewer/<reviewer_uuid>",
        "api_v3_datasets_assign_reviewer",
    ),
    ("/v3/reviews", "api_v3_reviews"),
    ("/v3/reviewers", "api_v3_reviewers"),
    # Admin
    ("/v3/admin/files-integrity-statistics", "api_v3_admin_files_integrity_statistics"),
    ("/v3/admin/accounts/clear-cache", "api_v3_admin_accounts_clear_cache"),
    ("/v3/admin/reviews/clear-cache", "api_v3_admin_reviews_clear_cache"),
    # Git protocol
    ("/v3/datasets/<git_uuid>.git", "api_v3_private_dataset_git_instructions"),
    ("/v3/datasets/<git_uuid>.git/info/refs", "api_v3_private_dataset_git_refs"),
    (
        "/v3/datasets/<git_uuid>.git/git-upload-pack",
        "api_v3_private_dataset_git_upload_pack",
    ),
    (
        "/v3/datasets/<git_uuid>.git/git-receive-pack",
        "api_v3_private_dataset_git_receive_pack",
    ),
    ("/v3/datasets/<git_uuid>.git/languages", "api_v3_dataset_git_languages"),
    ("/v3/datasets/<git_uuid>.git/contributors", "api_v3_dataset_git_contributors"),
    ("/v3/datasets/<git_uuid>.git/zip", "api_v3_dataset_git_zip"),
    # SSI
    ("/v3/receive-from-ssi", "api_v3_receive_from_ssi"),
    ("/v3/redirect-from-ssi/<container_uuid>/<token>", "api_v3_redirect_from_ssi"),
]


# A fake-but-syntactically-valid UUID for path placeholders. The route lookup
# only cares that the URL matches a Rule pattern — handlers may then return
# 4xx/5xx because the resource does not exist. That is fine: this file only
# asserts the route exists, not that the handler succeeds.
_FAKE_UUID = "00000000-0000-0000-0000-000000000000"
_PLACEHOLDERS = {
    "<dataset_id>": _FAKE_UUID,
    "<dataset_uuid>": _FAKE_UUID,
    "<container_uuid>": _FAKE_UUID,
    "<git_uuid>": _FAKE_UUID,
    "<collection_id>": _FAKE_UUID,
    "<account_id>": _FAKE_UUID,
    "<account_uuid>": _FAKE_UUID,
    "<author_id>": _FAKE_UUID,
    "<author_uuid>": _FAKE_UUID,
    "<file_id>": _FAKE_UUID,
    "<funding_id>": _FAKE_UUID,
    "<link_id>": _FAKE_UUID,
    "<collaborator_uuid>": _FAKE_UUID,
    "<reviewer_uuid>": _FAKE_UUID,
    "<category_id>": "1",
    "<version>": "1",
    "<item_type>": "datasets",
    "<token>": "placeholder",
}


def _concrete_path(template: str) -> str:
    """Substitute placeholder segments with fake-but-valid values."""
    out = template
    for placeholder, value in _PLACEHOLDERS.items():
        out = out.replace(placeholder, value)
    return out


# ---------------------------------------------------------------------------
# Source-of-truth extraction from src/djehuty/web/wsgi.py
# ---------------------------------------------------------------------------

# wsgi.py sits at <repo>/src/djehuty/web/wsgi.py; this file at
# <repo>/tests/e2e/tests/api/test_inventory.py — five parents up.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_WSGI_PY = _REPO_ROOT / "src" / "djehuty" / "web" / "wsgi.py"

# Match `R("/vN/...", self.handler_name)` rule registrations.
_RULE_RE = re.compile(
    r'^\s*R\("(?P<path>/v[23]/[^"]*)"\s*,\s*self\.(?P<handler>[A-Za-z_][A-Za-z_0-9]*)\)',
)


def _routes_from_wsgi():
    """Return ({v2_paths}, {v3_paths}) registered in wsgi.py.

    Comment lines (those starting with ``#`` after stripping) are skipped so
    string-literal paths mentioned in comments do not pollute the count.
    """
    v2, v3 = set(), set()
    for line in _WSGI_PY.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        match = _RULE_RE.match(line)
        if not match:
            continue
        path = match.group("path")
        if path.startswith("/v2/"):
            v2.add(path)
        else:
            v3.add(path)
    return v2, v3


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.api_inventory
def test_inventory_totals():
    """Sanity: 55 unique V2 + 60 V3 = 115 routes.

    Note: wsgi.py registers ``/v2/collections`` twice (both to ``api_collections``);
    we dedupe and count it once.
    """
    assert len(V2_ENDPOINTS) == 55, (
        f"V2 endpoint count drifted from 55 to {len(V2_ENDPOINTS)}; "
        f"verify src/djehuty/web/wsgi.py."
    )
    assert len(V3_ENDPOINTS) == 60, (
        f"V3 endpoint count drifted from 60 to {len(V3_ENDPOINTS)}; "
        f"verify src/djehuty/web/wsgi.py."
    )


@pytest.mark.api_inventory
def test_v2_inventory_matches_wsgi_py():
    """Every V2 path in wsgi.py is listed here, and vice versa."""
    real_v2, _ = _routes_from_wsgi()
    inventory_v2 = {path for path, _ in V2_ENDPOINTS}

    missing_from_inventory = real_v2 - inventory_v2
    extra_in_inventory = inventory_v2 - real_v2

    assert not missing_from_inventory and not extra_in_inventory, (
        f"V2 inventory drifted from src/djehuty/web/wsgi.py.\n"
        f"  Added in wsgi.py but missing here ({len(missing_from_inventory)}): "
        f"{sorted(missing_from_inventory)}\n"
        f"  Listed here but removed from wsgi.py ({len(extra_in_inventory)}): "
        f"{sorted(extra_in_inventory)}"
    )


@pytest.mark.api_inventory
def test_v3_inventory_matches_wsgi_py():
    """Every V3 path in wsgi.py is listed here, and vice versa."""
    _, real_v3 = _routes_from_wsgi()
    inventory_v3 = {path for path, _ in V3_ENDPOINTS}

    missing_from_inventory = real_v3 - inventory_v3
    extra_in_inventory = inventory_v3 - real_v3

    assert not missing_from_inventory and not extra_in_inventory, (
        f"V3 inventory drifted from src/djehuty/web/wsgi.py.\n"
        f"  Added in wsgi.py but missing here ({len(missing_from_inventory)}): "
        f"{sorted(missing_from_inventory)}\n"
        f"  Listed here but removed from wsgi.py ({len(extra_in_inventory)}): "
        f"{sorted(extra_in_inventory)}"
    )
