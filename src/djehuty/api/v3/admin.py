"""Administrative endpoints for the v3 API."""

import os

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, get_token, require_admin
from djehuty.api.exceptions import ForbiddenError, InvalidInputError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.v3._shared import _ok
from djehuty.web.config import config

router = APIRouter(tags=["V3 / Admin"])

_INTEGRITY_EXAMPLE = {
    "number_of_links": 3,
    "number_of_files": 1204,
    "number_of_bytes": 89123456789,
    "number_of_accessible_files": 1201,
    "number_of_inaccessible_files": 3,
    "number_of_incomplete_metadata": 1,
    "percentage_accessible": 99.75,
    "incomplete_metadata": ["9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8"],
    "missing_files": ["/data/storage/27e6a01d_9b1c3f2a"],
}


@router.get(
    "/admin/files-integrity-statistics",
    summary="File integrity statistics",
    responses={
        200: _ok("Storage integrity summary", _INTEGRITY_EXAMPLE),
        403: {"model": ErrorResponse},
    },
)
def files_integrity_statistics(
    token: str | None = Depends(get_token),
    db=Depends(get_db),
):
    # Legacy gates this on may_review_integrity (a separate privilege from
    # may_administer).
    if not token or not db.may_review_integrity(token):
        raise ForbiddenError("File-integrity reviewer permissions required.")

    files = db.repository_file_statistics(extended_properties=True)
    if not files:
        return JSONResponse(content={"message": "No files to check."})

    from djehuty.services.storage import filesystem_location
    from djehuty.utils.convenience import value_or
    from djehuty.web import s3

    number_of_files = 0
    number_of_inaccessible_files = 0
    number_of_incomplete_metadata = 0
    number_of_bytes = 0
    number_of_links = 0
    incomplete_metadata: list = []
    missing_files: list = []

    for entry in files:
        if value_or(entry, "is_link_only", False):
            number_of_links += 1
            continue
        number_of_files += 1
        number_of_bytes += int(float(entry.get("bytes", 0)))
        location = filesystem_location(entry)
        available_on_s3 = isinstance(location, s3.S3DownloadStreamer)
        if not (location or available_on_s3):
            number_of_incomplete_metadata += 1
            incomplete_metadata.append(value_or(entry, "uuid", "unknown"))
            continue
        if not ((isinstance(location, str) and os.path.isfile(location)) or available_on_s3):
            number_of_inaccessible_files += 1
            missing_files.append(location)

    return JSONResponse(
        content={
            "number_of_links": number_of_links,
            "number_of_files": number_of_files,
            "number_of_bytes": number_of_bytes,
            "number_of_accessible_files": number_of_files - number_of_inaccessible_files,
            "number_of_inaccessible_files": number_of_inaccessible_files,
            "number_of_incomplete_metadata": number_of_incomplete_metadata,
            "percentage_accessible": (
                (1.0 - (number_of_inaccessible_files / number_of_files)) * 100
                if number_of_files
                else 100.0
            ),
            "incomplete_metadata": incomplete_metadata,
            "missing_files": [str(f) for f in missing_files],
        }
    )


@router.get(
    "/admin/accounts/clear-cache",
    summary="Clear accounts cache",
    responses={204: {"description": "Accounts cache cleared"}, 403: {"model": ErrorResponse}},
)
def admin_clear_accounts_cache(account=Depends(require_admin), db=Depends(get_db)):
    db.cache.invalidate_by_prefix("accounts")
    return Response(status_code=204)


@router.get(
    "/admin/reviews/clear-cache",
    summary="Clear reviews cache",
    responses={204: {"description": "Reviews cache cleared"}, 403: {"model": ErrorResponse}},
)
def admin_clear_reviews_cache(account=Depends(require_admin), db=Depends(get_db)):
    db.cache.invalidate_by_prefix("reviews")
    return Response(status_code=204)


@router.post(
    "/datasets/{container_uuid}/repair_md5s",
    summary="Recompute MD5 checksums for files missing them",
    responses={
        201: _ok("Checksums regenerated", {"message": "The MD5 sums have been regenerated."}),
        403: {"model": ErrorResponse},
    },
)
def repair_md5s(
    container_uuid: str,
    token: str | None = Depends(get_token),
    db=Depends(get_db),
):
    import hashlib

    if not token or not db.may_administer(token):
        raise ForbiddenError("Administrator permissions required.")

    try:
        dataset = db.datasets(
            container_uuid=container_uuid,
            is_published=False,
            limit=1,
        )[0]
        account_uuid = dataset["account_uuid"]
    except (IndexError, AttributeError, KeyError) as error:
        raise InvalidInputError(
            f"Cannot find dataset or account UUID: {error}", "ResolveFailed"
        ) from error

    files = db.missing_checksummed_files_for_container(container_uuid)
    for row in files:
        file_uuid = row["file_uuid"]
        filename = os.path.join(config.storage, f"{container_uuid}_{file_uuid}")
        md5 = hashlib.new("md5", usedforsecurity=False)
        with open(filename, "rb") as stream:
            for chunk in iter(lambda f=stream: f.read(4096), b""):
                md5.update(chunk)
            computed = md5.hexdigest()
            db.update_file(
                account_uuid,
                file_uuid,
                dataset["uuid"],
                computed_md5=computed,
                filesystem_location=filename,
            )

    return JSONResponse(
        content={"message": "The MD5 sums have been regenerated."},
        status_code=201,
    )
