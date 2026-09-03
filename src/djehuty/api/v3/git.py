"""Git endpoints for the v3 API.

REST helpers:
  - GET    /v3/datasets/<dataset_id>.git/files
  - GET    /v3/datasets/<dataset_id>.git/branches
  - PUT    /v3/datasets/<dataset_id>.git/set-default-branch

Git smart-HTTP protocol (CGI-style passthrough to git-http-backend):
  - GET    /v3/datasets/<git_uuid>.git
  - GET    /v3/datasets/<git_uuid>.git/info/refs
  - POST   /v3/datasets/<git_uuid>.git/git-upload-pack
  - POST   /v3/datasets/<git_uuid>.git/git-receive-pack

Statistics:
  - GET    /v3/datasets/<git_uuid>.git/languages
  - GET    /v3/datasets/<git_uuid>.git/contributors
  - GET    /v3/datasets/<git_uuid>.git/zip
"""

from __future__ import annotations

import getpass
import logging
import os
import subprocess
from datetime import datetime

import pygit2
from fastapi import APIRouter, Body, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import (
    get_db,
    require_auth,
)
from djehuty.api.exceptions import (
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
)
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.services import git as git_service

router = APIRouter(tags=["V3 / Git"])
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# REST helpers
# ---------------------------------------------------------------------------


@router.get(
    "/datasets/{dataset_id}.git/files",
    summary="List files in default branch",
    responses={
        200: _ok("File names in the default branch", ["README.md", "analysis.py"]),
        403: {"model": ErrorResponse},
    },
)
def git_files(
    dataset_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    repository = git_service.repository_by_dataset_id(db, account["uuid"], dataset_id)
    if repository is None:
        raise NotFoundError()

    branch_name = git_service.default_branch_guess(repository)
    files: list = []
    if branch_name:
        try:
            tree = repository.revparse_single(branch_name).tree
            files = [entry.name for entry in tree]
        except pygit2.GitError as error:  # pylint: disable=no-member
            raise InvalidInputError(
                f"Failed to retrieve Git files for '{branch_name}' in '{repository.path}': {error}",
                "GitReadFailed",
            ) from error
    return JSONResponse(content=files)


@router.get(
    "/datasets/{dataset_id}.git/branches",
    summary="List branches + default",
    responses={
        200: _ok(
            "Local branches and the default branch",
            {"default-branch": "main", "branches": ["main", "dev"]},
        ),
        403: {"model": ErrorResponse},
    },
)
def git_branches(
    dataset_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    repository = git_service.repository_by_dataset_id(db, account["uuid"], dataset_id)
    if repository is None:
        raise NotFoundError()

    return JSONResponse(
        content={
            "default-branch": git_service.default_branch_guess(repository),
            "branches": list(repository.branches.local),
        }
    )


@router.put(
    "/datasets/{dataset_id}.git/set-default-branch",
    summary="Set the repository's default branch",
    responses={204: {"description": "Default branch set"}, 403: {"model": ErrorResponse}},
)
def git_set_default_branch(
    dataset_id: str,
    body: dict = Body(
        ...,
        openapi_examples={
            "default": {"summary": "Set the default branch", "value": {"branch": "main"}}
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    # AS-IS: setting the default branch is a write -> requires data_edit.
    repository = git_service.repository_by_dataset_id(
        db, account["uuid"], dataset_id, action="edit"
    )
    if repository is None:
        raise NotFoundError()

    branch_name = body.get("branch") if isinstance(body, dict) else None
    if not isinstance(branch_name, str):
        raise InvalidInputError("Field 'branch' is required.", "BadBranch")
    if branch_name not in repository.branches.local:
        raise InvalidInputError(f"Branch '{branch_name}' does not exist.", "UnknownBranch")

    if not git_service.set_default_branch(repository, branch_name):
        raise InvalidInputError("Failed to set default branch.", "SetDefaultFailed")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Smart-HTTP protocol passthrough
#
# git-http-backend(1) is a CGI program shipped with git that handles the
# upload-pack / receive-pack flow. We invoke it as a subprocess and stream
# its stdout back to the client.
# ---------------------------------------------------------------------------


def _repository_path(git_uuid: str) -> str:
    """Return the on-disk path of the bare repository."""
    from djehuty.web.config import config

    return os.path.join(config.storage, f"{git_uuid}.git")


def _git_directory(git_uuid: str) -> str | None:
    """Return the on-disk path of the bare repository, or None if missing."""
    path = _repository_path(git_uuid)
    return path if os.path.exists(path) else None


def _log_event(db, request: Request, item_uuid: str, item_type: str, event_type: str):
    """Record a view or download event, mirroring legacy ``__log_event``."""
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    ip_address = request.headers.get("x-forwarded-for")
    if ip_address is None and request.client is not None:
        ip_address = request.client.host
    return db.insert_log_entry(
        timestamp, ip_address, item_uuid, item_type=item_type, event_type=event_type
    )


@router.get("/datasets/{git_uuid}.git", summary="Git smart-HTTP instructions")
def git_instructions(git_uuid: str, db=Depends(get_db)):
    from djehuty.web import validator
    from djehuty.web.config import config

    if not validator.is_valid_uuid(git_uuid):
        raise NotFoundError()

    try:
        # AS-IS: only consider published datasets to not reveal whether a
        # UUID is reserved for a Git repository.
        db.datasets(git_uuid=git_uuid, is_published=True, is_latest=None)[0]
    except IndexError as error:
        raise NotFoundError() from error

    clone_url = f"{config.base_url}/v3/datasets/{git_uuid}.git"
    return Response(
        content=(
            f"This is a Djehuty-backed git repository.\n"
            f"Use git clone {clone_url} for read access.\n"
        ),
        media_type="text/plain",
    )


def _git_cgi(
    repository_path: str,
    environ: dict,
    body: bytes | None = None,
) -> tuple[int, dict, bytes]:
    """Invoke git-http-backend(1) and capture its (status, headers, body)."""
    env = {**os.environ}
    env.update(environ)
    env["GIT_PROJECT_ROOT"] = os.path.dirname(repository_path)
    env["GIT_HTTP_EXPORT_ALL"] = "1"
    env["REMOTE_USER"] = getpass.getuser()
    env["PATH_INFO"] = "/" + os.path.basename(repository_path) + env.get("PATH_INFO", "")
    env.pop("HTTP_AUTHORIZATION", None)

    process = subprocess.run(
        ["git", "http-backend"],
        input=body or b"",
        capture_output=True,
        env=env,
        check=False,
    )
    if process.returncode != 0:
        _log.error("Proxying to Git failed with exit code %d", process.returncode)
        return 500, {}, b""
    raw = process.stdout
    headers: dict = {}
    status_code = 200
    # CGI response: headers terminated by blank line.
    if b"\r\n\r\n" in raw:
        header_block, payload = raw.split(b"\r\n\r\n", 1)
    elif b"\n\n" in raw:
        header_block, payload = raw.split(b"\n\n", 1)
    else:
        header_block, payload = b"", raw

    for line in header_block.decode("latin-1", errors="replace").splitlines():
        if ":" not in line:
            continue
        name, _, value = line.partition(":")
        name = name.strip()
        value = value.strip()
        if name.lower() == "status":
            try:
                status_code = int(value.split()[0])
            except ValueError:
                pass
        else:
            headers[name] = value
    return status_code, headers, payload


def _git_protocol(request: Request) -> str:
    """Return the Git-Protocol header value to forward, as legacy does."""
    return request.headers.get("git-protocol", "version 2")


def _upload_pack_gate(db, request: Request, git_uuid: str) -> None:
    """Unauthenticated upload-pack gate, mirroring legacy.

    The dataset must resolve regardless of publication state, and every
    fetch is recorded as a gitDownload event.
    """
    from djehuty.web import validator

    if not validator.is_valid_uuid(git_uuid):
        raise ForbiddenError()
    try:
        dataset = db.datasets(git_uuid=git_uuid, is_published=None, is_latest=None)[0]
    except IndexError as error:
        raise ForbiddenError() from error
    if dataset is None:
        raise ForbiddenError()
    _log_event(db, request, dataset["container_uuid"], "dataset", "gitDownload")


def _receive_pack_refs_gate(db, git_uuid: str) -> None:
    """Ref-advertisement gate for pushes, mirroring legacy.

    AS-IS: unauthenticated -- a draft dataset carrying the git_uuid must
    exist, nothing more. The actual pack transfer (git-receive-pack POST)
    does require an authenticated owner or collaborator.
    """
    from djehuty.web import validator

    if not validator.is_valid_uuid(git_uuid):
        raise ForbiddenError()
    try:
        dataset = db.datasets(git_uuid=git_uuid, is_published=False)[0]
    except IndexError as error:
        raise ForbiddenError() from error
    if dataset is None:
        raise ForbiddenError()


@router.get("/datasets/{git_uuid}.git/info/refs", summary="git info/refs")
def git_info_refs(
    git_uuid: str,
    request: Request,
    service: str | None = Query(None, max_length=16),
    db=Depends(get_db),
):
    from djehuty.web import validator

    # git_uuid becomes a filesystem path below; reject anything that is not a
    # UUID before it reaches create_repository / the CGI path. Valid ids are
    # unaffected, so this does not change behaviour for real requests.
    if not validator.is_valid_uuid(git_uuid):
        raise NotFoundError()

    # AS-IS: the bare repository is created unconditionally, before any
    # dataset gate runs.
    git_service.create_repository(git_uuid)

    if service == "git-upload-pack":
        _upload_pack_gate(db, request, git_uuid)
    elif service == "git-receive-pack":
        _receive_pack_refs_gate(db, git_uuid)
    else:
        _log.error("Unsupported Git service command: %s.", service)
        return Response(content="", status_code=500)

    env = {
        "REQUEST_METHOD": "GET",
        "QUERY_STRING": str(request.url.query),
        "PATH_INFO": "/info/refs",
        "GIT_PROTOCOL": _git_protocol(request),
    }
    status, headers, payload = _git_cgi(_repository_path(git_uuid), env)
    return Response(content=payload, status_code=status, headers=headers)


@router.post("/datasets/{git_uuid}.git/git-upload-pack", summary="git-upload-pack")
async def git_upload_pack(
    git_uuid: str,
    request: Request,
    db=Depends(get_db),
):
    _upload_pack_gate(db, request, git_uuid)
    body = await request.body()
    env = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": request.headers.get(
            "content-type", "application/x-git-upload-pack-request"
        ),
        "CONTENT_LENGTH": str(len(body)),
        "PATH_INFO": "/git-upload-pack",
        "GIT_PROTOCOL": _git_protocol(request),
    }
    status, headers, payload = _git_cgi(_repository_path(git_uuid), env, body=body)
    return Response(content=payload, status_code=status, headers=headers)


@router.post("/datasets/{git_uuid}.git/git-receive-pack", summary="git-receive-pack")
async def git_receive_pack(
    git_uuid: str,
    request: Request,
    db=Depends(get_db),
):
    # AS-IS: legacy accepts the push unauthenticated -- a draft dataset
    # carrying this git_uuid must exist, nothing more.
    _receive_pack_refs_gate(db, git_uuid)
    repo_path = _repository_path(git_uuid)
    body = await request.body()
    env = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": request.headers.get(
            "content-type", "application/x-git-receive-pack-request"
        ),
        "CONTENT_LENGTH": str(len(body)),
        "PATH_INFO": "/git-receive-pack",
        "GIT_PROTOCOL": _git_protocol(request),
    }
    status, headers, payload = _git_cgi(repo_path, env, body=body)
    return Response(content=payload, status_code=status, headers=headers)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _statistics_repository(db, git_uuid: str) -> tuple:
    """Resolve GIT_UUID to (repository, default branch) for statistics.

    Mirrors legacy ``__git_statistics_error_handling``: an invalid UUID is
    400, an unknown dataset or missing repository is 404. The default branch
    is None when the repository has no branches.
    """
    from djehuty.web import validator
    from djehuty.web.config import config

    if not validator.is_valid_uuid(git_uuid):
        # AS-IS: legacy's misspelled error code.
        raise InvalidInputError("Invalid UUID.", "InvalidGitUUIError")

    if not db.datasets(git_uuid=git_uuid, is_published=None, is_latest=None):
        _log.error("No dataset associated with Git repository '%s'.", git_uuid)
        raise NotFoundError()

    git_directory = os.path.join(config.storage, f"{git_uuid}.git")
    if not os.path.exists(git_directory):
        _log.error("No Git repository at '%s'", git_directory)
        raise NotFoundError()

    repository = pygit2.Repository(git_directory)
    return repository, git_service.default_branch_guess(repository)


@router.get(
    "/datasets/{git_uuid}.git/languages",
    summary="Languages in default branch",
    responses={
        200: _ok("Bytes per language in the default branch", {"Python": 51234, "Other": 220})
    },
)
def git_languages(git_uuid: str, db=Depends(get_db)):
    repository, default_branch = _statistics_repository(db, git_uuid)
    if not default_branch:
        raise NotFoundError()

    content = git_service.languages_summary(db, git_uuid, repository)
    return Response(content=content, media_type="application/json")


@router.get(
    "/datasets/{git_uuid}.git/contributors",
    summary="Contributor statistics",
    responses={
        200: _ok(
            "GitHub-style commit statistics per author e-mail",
            [
                {
                    "total": 42,
                    "additions": 1200,
                    "deletions": 34,
                    "weeks": [{"w": 1704668400, "a": 100, "d": 3, "c": 2}],
                    "author": {"name": "Ada Lovelace", "email": "ada@example.org"},
                }
            ],
        )
    },
)
def git_contributors(git_uuid: str, db=Depends(get_db)):
    repository, default_branch = _statistics_repository(db, git_uuid)
    if not default_branch:
        raise NotFoundError()

    contributors = git_service.contributors(db, git_uuid, repository)
    if contributors is None:
        raise NotFoundError()
    return JSONResponse(content=contributors)


@router.get("/datasets/{git_uuid}.git/zip", summary="Default branch as zip")
def git_zip(git_uuid: str, db=Depends(get_db)):
    import io
    import zipfile

    repository, branch_name = _statistics_repository(db, git_uuid)
    if branch_name is None:
        raise InvalidInputError("No default branch found.", "NoGitBranch")
    try:
        tree = repository.revparse_single(branch_name).tree
    except pygit2.GitError as error:  # pylint: disable=no-member
        raise NotFoundError() from error

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        def _walk(t, prefix=""):
            for entry in t:
                if isinstance(entry, pygit2.Tree):  # pylint: disable=no-member
                    _walk(entry, prefix=f"{prefix}{entry.name}/")
                elif isinstance(entry, pygit2.Commit):  # pylint: disable=no-member
                    continue
                else:
                    blob = repository[entry.id]
                    zf.writestr(f"{prefix}{entry.name}", blob.data)

        _walk(tree)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": (f'attachment; filename="{git_uuid}.zip"')},
    )
