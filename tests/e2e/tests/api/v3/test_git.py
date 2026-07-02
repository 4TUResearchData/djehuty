"""
V3 Git API contract tests.

REST-style git helpers (3):
    GET    /v3/datasets/<dataset_id>.git/files
    GET    /v3/datasets/<dataset_id>.git/branches
    PUT    /v3/datasets/<dataset_id>.git/set-default-branch

Git smart-HTTP protocol endpoints (7):
    GET    /v3/datasets/<git_uuid>.git
    GET    /v3/datasets/<git_uuid>.git/info/refs
    POST   /v3/datasets/<git_uuid>.git/git-upload-pack
    POST   /v3/datasets/<git_uuid>.git/git-receive-pack
    GET    /v3/datasets/<git_uuid>.git/languages
    GET    /v3/datasets/<git_uuid>.git/contributors
    GET    /v3/datasets/<git_uuid>.git/zip

These tests exercise the routes' authentication and method enforcement.
Full git-protocol verification requires an actual git client and is out of
scope here — those interactions are best covered by integration tests.

Run with:
    cd tests/e2e && python -m pytest tests/api/v3/test_git.py -v
"""

import uuid

from playwright.sync_api import Page


# ---------------------------------------------------------------------------
# REST helpers
# ---------------------------------------------------------------------------


class TestV3GitFilesApi:
    """GET /v3/datasets/<id>.git/files."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}.git/files")
        save_response(response, "v3-git-files-no-auth")
        assert response.status in (401, 403)

    def test_rejects_post(self, page: Page, save_response):
        """POST → 405."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/datasets/{fake}.git/files",
            data={},
        )
        save_response(response, "v3-git-files-post")
        assert response.status == 405

    def test_nonexistent_dataset_returns_404(
        self, authenticated_page: Page, save_response
    ):
        """Authenticated GET on a fake dataset → 404."""
        fake = str(uuid.uuid4())
        response = authenticated_page.request.get(f"/v3/datasets/{fake}.git/files")
        save_response(response, "v3-git-files-fake")
        assert response.status == 404


class TestV3GitBranchesApi:
    """GET /v3/datasets/<id>.git/branches."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}.git/branches")
        save_response(response, "v3-git-branches-no-auth")
        assert response.status in (401, 403)

    def test_rejects_post(self, page: Page, save_response):
        """POST → 405."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/datasets/{fake}.git/branches",
            data={},
        )
        save_response(response, "v3-git-branches-post")
        assert response.status == 405

    def test_nonexistent_dataset_returns_404(
        self, authenticated_page: Page, save_response
    ):
        """Authenticated GET on a fake dataset → 404."""
        fake = str(uuid.uuid4())
        response = authenticated_page.request.get(f"/v3/datasets/{fake}.git/branches")
        save_response(response, "v3-git-branches-fake")
        assert response.status == 404


class TestV3GitSetDefaultBranchApi:
    """PUT /v3/datasets/<id>.git/set-default-branch."""

    def test_requires_auth(self, page: Page, save_response):
        """Unauthenticated → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.put(
            f"/v3/datasets/{fake}.git/set-default-branch",
            data={"branch": "main"},
        )
        save_response(response, "v3-git-set-branch-no-auth")
        assert response.status in (401, 403)


# ---------------------------------------------------------------------------
# Smart-HTTP protocol endpoints
# ---------------------------------------------------------------------------


class TestV3GitProtocolEndpoints:
    """Git smart-HTTP protocol endpoints — only structural checks here."""

    def test_git_instructions_unauth(self, page: Page, save_response):
        """GET /v3/datasets/<uuid>.git unauthenticated.

        AS-IS: returns 404 (does not reveal whether the dataset exists).
        Other .git/* endpoints return 401/403 in the same situation —
        inconsistent but locked here.
        """
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}.git")
        save_response(response, "v3-git-instructions-no-auth")
        assert response.status in (401, 403, 404)

    def test_git_info_refs_requires_auth(self, page: Page, save_response):
        """GET .../info/refs without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.get(
            f"/v3/datasets/{fake}.git/info/refs?service=git-upload-pack"
        )
        save_response(response, "v3-git-info-refs-no-auth")
        assert response.status in (401, 403)

    def test_git_upload_pack_requires_auth(self, page: Page, save_response):
        """POST .../git-upload-pack without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/datasets/{fake}.git/git-upload-pack",
            data="",
            headers={"Content-Type": "application/x-git-upload-pack-request"},
        )
        save_response(response, "v3-git-upload-pack-no-auth")
        assert response.status in (401, 403)

    def test_git_receive_pack_requires_auth(self, page: Page, save_response):
        """POST .../git-receive-pack without auth → 401/403."""
        fake = str(uuid.uuid4())
        response = page.request.post(
            f"/v3/datasets/{fake}.git/git-receive-pack",
            data="",
            headers={"Content-Type": "application/x-git-receive-pack-request"},
        )
        save_response(response, "v3-git-receive-pack-no-auth")
        assert response.status in (401, 403)

    def test_git_languages_nonexistent_returns_4xx(self, page: Page, save_response):
        """GET .../languages on missing dataset → 4xx."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}.git/languages")
        save_response(response, "v3-git-languages-fake")
        assert 400 <= response.status < 500

    def test_git_contributors_nonexistent_returns_4xx(self, page: Page, save_response):
        """GET .../contributors on missing dataset → 4xx."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}.git/contributors")
        save_response(response, "v3-git-contributors-fake")
        assert 400 <= response.status < 500

    def test_git_zip_nonexistent_returns_4xx(self, page: Page, save_response):
        """GET .../zip on missing dataset → 4xx."""
        fake = str(uuid.uuid4())
        response = page.request.get(f"/v3/datasets/{fake}.git/zip")
        save_response(response, "v3-git-zip-fake")
        assert 400 <= response.status < 500
