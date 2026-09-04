"""
V3 Authors & Account search API contract tests.

Endpoints (2):
    POST /v3/accounts/search
    GET  /v3/authors/<author_uuid>

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_authors.py -v
"""

import uuid

from helpers.contract import assert_status
from playwright.sync_api import Page


class TestV3AccountsSearchApi:
    """POST /v3/accounts/search — typeahead account lookup (auth required)."""

    def test_search_requires_auth(self, page: Page, save_response):
        """POST /v3/accounts/search without auth → 401/403."""
        response = page.request.post(
            "/v3/accounts/search",
            data={"search_for": "test"},
        )
        save_response(response, "v3-accounts-search-no-auth")
        assert response.status in (401, 403)

    def test_accounts_search(self, authenticated_page: Page, save_response):
        """POST /v3/accounts/search authenticated → 200, JSON array."""
        response = authenticated_page.request.post(
            "/v3/accounts/search",
            data={"search_for": "dev"},
        )
        save_response(response, "v3-accounts-search")
        assert_status(
            response,
            expected=200,
            current_bug=500,
            bug="#111: POST /v3/accounts/search crashes on a simple valid body",
        )
        if response.status == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_accounts_search_get_requires_auth(self, page: Page, save_response):
        """GET /v3/accounts/search unauthenticated → 403 (auth checked first)."""
        response = page.request.get("/v3/accounts/search")
        save_response(response, "v3-accounts-search-get-rejected")
        # AS-IS: this handler checks auth before method, so an unauth GET is
        # 403, not the 405 you'd expect from a method-enforcement test.
        assert response.status == 403


class TestV3AuthorDetailsApi:
    """GET /v3/authors/<uuid> — author by UUID (auth required)."""

    def test_author_requires_auth(self, page: Page, save_response):
        """GET /v3/authors/<fake> without auth → 403 (auth is checked first)."""
        fake_uuid = str(uuid.uuid4())
        response = page.request.get(f"/v3/authors/{fake_uuid}")
        save_response(response, "v3-author-no-auth")
        assert response.status == 403

    def test_nonexistent_author_returns_404(self, authenticated_page: Page, save_response):
        """GET /v3/authors/<fake> authenticated → 404."""
        fake_uuid = str(uuid.uuid4())
        response = authenticated_page.request.get(f"/v3/authors/{fake_uuid}")
        save_response(response, "v3-author-404")
        assert response.status == 404

    def test_update_manual_author_rejects_active_email(self, draft_dataset, save_response):
        """PUT rejects an email edition of a manual author matching an active author."""
        page, container_uuid = draft_dataset
        manual_email = "manual-author@example.invalid"

        create_response = page.request.put(
            f"/v2/account/articles/{container_uuid}/authors",
            data={
                "authors": [
                    {
                        "first_name": "Manual",
                        "last_name": "Author",
                        "email": manual_email,
                    }
                ]
            },
        )
        save_response(create_response, "v3-author-active-email-create")
        assert create_response.ok

        authors_response = page.request.get(f"/v2/account/articles/{container_uuid}/authors")
        save_response(authors_response, "v3-author-active-email-create-verify")
        authors = authors_response.json()
        assert len(authors) == 1
        manual_uuid = authors[0]["uuid"]

        before_response = page.request.get(f"/v3/datasets/{container_uuid}/authors/{manual_uuid}")
        save_response(before_response, "v3-author-active-email-before")
        before_author = before_response.json()

        response = page.request.put(
            f"/v3/authors/{manual_uuid}",
            data={
                "first_name": "Manual",
                "last_name": "Author",
                "email": "  Dev@DJEHUTY.COM  ",
                "orcid": "",
            },
        )
        save_response(response, "v3-author-active-email-conflict")
        assert response.status == 409
        assert response.json()["message"] == (
            "An active author with this email address or ORCID already exists. "
            "Remove this manual author and select the existing author from "
            "the autocomplete."
        )

        after_response = page.request.get(f"/v3/datasets/{container_uuid}/authors/{manual_uuid}")
        save_response(after_response, "v3-author-active-email-after")
        assert after_response.json() == before_author

    def test_update_manual_author_allows_inactive_email(self, draft_dataset, save_response):
        """PUT allows editing a manual author to use an inactive author's email."""
        page, container_uuid = draft_dataset
        matching_email = "inactive-author@example.invalid"

        matching_response = page.request.put(
            f"/v2/account/articles/{container_uuid}/authors",
            data={
                "authors": [
                    {
                        "first_name": "Matching",
                        "last_name": "Author",
                        "email": matching_email,
                    }
                ]
            },
        )
        save_response(matching_response, "v3-author-inactive-email-create-matching")
        assert matching_response.ok

        matching_authors_response = page.request.get(
            f"/v2/account/articles/{container_uuid}/authors"
        )
        save_response(matching_authors_response, "v3-author-inactive-email-create-matching-verify")
        assert matching_authors_response.status == 200
        matching_authors = matching_authors_response.json()
        assert len(matching_authors) == 1
        assert matching_authors[0].get("is_active") is False
        matching_uuid = matching_authors[0]["uuid"]

        edited_response = page.request.post(
            f"/v2/account/articles/{container_uuid}/authors",
            data={
                "authors": [
                    {
                        "first_name": "Edited",
                        "last_name": "Author",
                        "email": "edited-author@example.invalid",
                    }
                ]
            },
        )
        save_response(edited_response, "v3-author-inactive-email-create-edited")
        assert edited_response.ok

        edited_authors_response = page.request.get(f"/v2/account/articles/{container_uuid}/authors")
        save_response(edited_authors_response, "v3-author-inactive-email-create-edited-verify")
        assert edited_authors_response.status == 200
        edited_authors = edited_authors_response.json()
        assert len(edited_authors) == 2

        edited_author = next(
            author
            for author in edited_authors
            if author["uuid"] != matching_uuid
        )
        assert edited_author.get("is_active") is False
        edited_uuid = edited_author["uuid"]
        assert edited_uuid != matching_uuid

        matching_before_response = page.request.get(
            f"/v3/datasets/{container_uuid}/authors/{matching_uuid}"
        )
        save_response(matching_before_response, "v3-author-inactive-email-matching-before")
        assert matching_before_response.status == 200
        matching_before = matching_before_response.json()
        assert matching_before["email"] == matching_email

        response = page.request.put(
            f"/v3/authors/{edited_uuid}",
            data={
                "first_name": "Edited",
                "last_name": "Author",
                "email": matching_email,
                "orcid": "",
            },
        )
        save_response(response, "v3-author-inactive-email-update")
        assert response.status == 204

        edited_after_response = page.request.get(
            f"/v3/datasets/{container_uuid}/authors/{edited_uuid}"
        )
        save_response(edited_after_response, "v3-author-inactive-email-edited-after")
        assert edited_after_response.status == 200
        edited_after = edited_after_response.json()
        assert edited_after["uuid"] == edited_uuid
        assert edited_after["email"] == matching_email

        matching_after_response = page.request.get(
            f"/v3/datasets/{container_uuid}/authors/{matching_uuid}"
        )
        save_response(matching_after_response, "v3-author-inactive-email-matching-after")
        assert matching_after_response.status == 200
        assert matching_after_response.json() == matching_before

    def test_update_manual_author_rejects_active_orcid(self, draft_dataset, save_response):
        """PUT rejects an orcid edition of a manual author matching an active author."""
        page, container_uuid = draft_dataset

        active_response = page.request.get(f"/v2/account/articles/{container_uuid}/authors")
        save_response(active_response, "v3-author-active-orcid-existing")
        assert active_response.status == 200

        active_authors = active_response.json()
        assert len(active_authors) == 1
        active_author = active_authors[0]
        assert active_author.get("is_active") is True
        existing_orcid = active_author["orcid_id"]

        manual_email = "manual-author@example.invalid"
        manual_orcid = "0000-0000-0000-0028"

        create_response = page.request.put(
            f"/v2/account/articles/{container_uuid}/authors",
            data={
                "authors": [
                    {
                        "first_name": "Manual",
                        "last_name": "Author",
                        "email": manual_email,
                        "orcid_id": manual_orcid,
                    }
                ]
            },
        )
        save_response(create_response, "v3-author-active-orcid-create")
        assert create_response.ok

        authors_response = page.request.get(f"/v2/account/articles/{container_uuid}/authors")
        save_response(authors_response, "v3-author-active-orcid-create-verify")
        authors = authors_response.json()
        assert len(authors) == 1
        manual_uuid = authors[0]["uuid"]

        before_response = page.request.get(f"/v3/authors/{manual_uuid}")
        save_response(before_response, "v3-author-active-orcid-before")
        assert before_response.status == 200
        before_author = before_response.json()

        response = page.request.put(
            f"/v3/authors/{manual_uuid}",
            data={
                "first_name": "Manual",
                "last_name": "Author",
                "email": manual_email,
                "orcid": f"https://orcid.org/{existing_orcid}",
            },
        )
        save_response(response, "v3-author-active-orcid-conflict")
        assert response.status == 409
        assert response.json()["message"] == (
            "An active author with this email address or ORCID already exists. "
            "Remove this manual author and select the existing author from "
            "the autocomplete."
        )

        after_response = page.request.get(f"/v3/authors/{manual_uuid}")
        save_response(after_response, "v3-author-active-orcid-after")
        assert after_response.status == 200
        assert after_response.json() == before_author

    def test_update_manual_author_allows_inactive_orcid(self, draft_dataset, save_response):
        """PUT allows an ORCID matching an inactive author."""
        page, container_uuid = draft_dataset
        matching_orcid = "0000-0000-0000-0028"

        matching_response = page.request.put(
            f"/v2/account/articles/{container_uuid}/authors",
            data={
                "authors": [
                    {
                        "first_name": "Matching",
                        "last_name": "Author",
                        "email": "matching-author@example.invalid",
                        "orcid_id": matching_orcid,
                    }
                ]
            },
        )
        save_response(matching_response, "v3-author-inactive-orcid-create-matching")
        assert matching_response.ok

        matching_authors_response = page.request.get(
            f"/v2/account/articles/{container_uuid}/authors"
        )
        save_response(matching_authors_response, "v3-author-inactive-orcid-create-matching-verify")
        matching_authors = matching_authors_response.json()
        assert len(matching_authors) == 1
        assert matching_authors[0].get("is_active") is False
        matching_uuid = matching_authors[0]["uuid"]

        edited_email = "edited-author@example.invalid"

        edited_response = page.request.put(
            f"/v2/account/articles/{container_uuid}/authors",
            data={
                "authors": [
                    {
                        "first_name": "Edited",
                        "last_name": "Author",
                        "email": edited_email,
                        "orcid_id": "0000-0000-0000-0036",
                    }
                ]
            },
        )
        save_response(edited_response, "v3-author-inactive-orcid-create-edited")
        assert edited_response.ok

        edited_authors_response = page.request.get(f"/v2/account/articles/{container_uuid}/authors")
        save_response(edited_authors_response, "v3-author-inactive-orcid-create-edited-verify")
        edited_authors = edited_authors_response.json()
        assert len(edited_authors) == 1
        assert edited_authors[0].get("is_active") is False
        edited_uuid = edited_authors[0]["uuid"]
        assert edited_uuid != matching_uuid

        matching_before_response = page.request.get(f"/v3/authors/{matching_uuid}")
        save_response(matching_before_response, "v3-author-inactive-orcid-matching-before")
        assert matching_before_response.status == 200
        matching_before = matching_before_response.json()

        response = page.request.put(
            f"/v3/authors/{edited_uuid}",
            data={
                "first_name": "Edited",
                "last_name": "Author",
                "email": edited_email,
                "orcid": f"https://orcid.org/{matching_orcid}",
            },
        )
        save_response(response, "v3-author-inactive-orcid-update")
        assert response.status == 204

        edited_after_response = page.request.get(f"/v3/authors/{edited_uuid}")
        save_response(edited_after_response, "v3-author-inactive-orcid-edited-after")
        assert edited_after_response.status == 200
        edited_after = edited_after_response.json()
        assert edited_after["uuid"] == edited_uuid
        assert edited_after["orcid"] == matching_orcid

        matching_after_response = page.request.get(f"/v3/authors/{matching_uuid}")
        save_response(matching_after_response, "v3-author-inactive-orcid-matching-after")
        assert matching_after_response.status == 200
        assert matching_after_response.json() == matching_before
