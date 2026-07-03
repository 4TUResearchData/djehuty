"""Dataset file endpoints for the v3 API."""

import hashlib
import logging
import os

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from djehuty.api.dependencies import get_db, get_token, require_auth
from djehuty.api.exceptions import ForbiddenError, InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.permissions import enforce_collaborative_permissions
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.datasets._shared import _resolve_dataset
from djehuty.web import formatter
from djehuty.web.config import config
from djehuty.web.locks import Locks

router = APIRouter(tags=["V3 / Datasets / Files"])
logger = logging.getLogger(__name__)

# One process-wide instance, as legacy creates at server init. Instantiating
# Locks() per request would re-run its __init__ and replace held locks.
_process_locks = Locks()

_IMAGE_FILE_EXAMPLE = {
    "id": None,
    "uuid": "9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8",
    "name": "map-overview.png",
    "size": 248193,
    "is_link_only": False,
    "is_incomplete": False,
    "download_url": "https://data.4tu.nl/file/27e6a01d-3f09-4d90-ae02-1d749ae9efb8/9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8",
    "supplied_md5": "0cc175b9c0f1b6a831c399e269772661",
    "computed_md5": "0cc175b9c0f1b6a831c399e269772661",
}

_UPLOAD_LOCATION_EXAMPLE = {
    "location": "https://data.4tu.nl/v3/file/9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8"
}


@router.get(
    "/datasets/{dataset_id}/image-files",
    summary="List image files",
    responses={
        200: _ok("The dataset's image files", [_IMAGE_FILE_EXAMPLE]),
        403: {"model": ErrorResponse},
    },
)
def list_image_files(
    dataset_id: str, request: Request, account=Depends(require_auth), db=Depends(get_db)
):
    from djehuty.web import validator

    dataset = _resolve_dataset(db, dataset_id, account["uuid"])
    args = request.query_params
    try:
        files = db.dataset_files(
            dataset_uri=dataset["uri"],
            account_uuid=account["uuid"],
            limit=validator.integer_value(args, "limit"),
            order=validator.integer_value(args, "order"),
            order_direction=validator.order_direction(args, "order_direction"),
            is_image=True,
        )
        return JSONResponse(
            content=[
                formatter.format_file_for_dataset_record({"base_url": config.base_url, **f})
                for f in files
            ]
        )
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error


# ---------------------------------------------------------------------------
# Upload
#
# Native FastAPI port of /v3/datasets/<id>/upload. Same observable behaviour
# as the legacy ``api_v3_dataset_upload_file`` (status codes, response shape,
# storage path layout, MD5 strict-check semantics), but implemented using
# Starlette's built-in multipart parser (via ``UploadFile``) instead of the
# legacy's manual byte-level boundary parsing. Once api-service=new is the
# only configuration, the legacy 500-line implementation can be deleted.
# ---------------------------------------------------------------------------

_UPLOAD_CHUNK_SIZE = 4096
_EMPTY_FILE_MD5 = "d41d8cd98f00b204e9800998ecf8427e"


@router.post(
    "/datasets/{dataset_id}/upload",
    summary="Upload a file to a dataset",
    description=(
        "Stream-upload a single file into a draft dataset.\n\n"
        "Request body must be ``multipart/form-data`` with one file part.\n\n"
        "Query parameters:\n"
        "- ``strict_check=1`` — reject empty files, duplicate MD5s, and "
        "MD5 mismatches; the ``md5`` parameter becomes required.\n"
        "- ``md5`` — 32-character hex MD5 of the file's contents (required "
        "when ``strict_check=1``).\n\n"
        "Responses:\n"
        '- ``200`` — file accepted, ``{"location": "<base>/v3/file/<uuid>"}``\n'
        "- ``400`` — empty file, malformed body, or MD5 mismatch\n"
        "- ``403`` — account has no quota or no permission to edit dataset\n"
        "- ``409`` — duplicate file (only when ``strict_check=1``)\n"
        "- ``413`` — file exceeds remaining quota\n"
        "- ``415`` — not multipart/form-data"
    ),
    responses={
        200: _ok("File accepted", _UPLOAD_LOCATION_EXAMPLE),
        403: {"model": ErrorResponse},
    },
)
async def upload_file(
    dataset_id: str,
    request: Request,
    account=Depends(require_auth),
    db=Depends(get_db),
    token: str | None = Depends(get_token),
):
    from djehuty.web import validator
    from djehuty.web.locks import LockTypes

    account_uuid = account["uuid"]
    args = request.query_params

    # Quota check.
    account_record = db.account_by_uuid(account_uuid)
    if account_record is None or "quota" not in account_record:
        raise ForbiddenError(
            f"account:{account_uuid} attempted to upload a file but has no assigned quota."
        )

    storage_used = db.account_storage_used(account_uuid)
    storage_available = account_record["quota"] - storage_used
    if storage_available < 1:
        raise HTTPException(status_code=413, detail="Quota exhausted.")

    strict_check = validator.integer_value(args, "strict_check", 0, 1)
    supplied_md5 = None
    if strict_check:
        try:
            supplied_md5 = validator.string_value(
                args, "md5", minimum_length=32, maximum_length=32, required=True
            )
        except validator.ValidationException as error:
            raise InvalidInputError(error.message, error.code) from error
        if supplied_md5 == _EMPTY_FILE_MD5:
            raise InvalidInputError("Empty file is not allowed.", "EmptyFile")

    # Dataset ownership check (must be the owner's draft).
    try:
        dataset = _resolve_dataset(db, dataset_id, account_uuid)
    except NotFoundError as error:
        raise ForbiddenError(
            f"account:{account_uuid} attempted to upload a file to dataset:{dataset_id}."
        ) from error
    # AS-IS: a collaborator needs data_edit to upload; owners no-op.
    enforce_collaborative_permissions(db, account_uuid, dataset, "dataset", "data_edit")

    if strict_check:
        for existing in db.dataset_files(dataset_uri=dataset["uri"], account_uuid=account_uuid):
            if "computed_md5" not in existing:
                continue
            if existing["computed_md5"] == supplied_md5:
                raise HTTPException(
                    status_code=409,
                    detail="A file with the same MD5 is already attached.",
                )

    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        return Response(status_code=415)

    content_length = request.headers.get("content-length")
    if content_length is None:
        logger.error("File upload failed due to missing Content-Length.")
        raise InvalidInputError("Missing Content-Length header.", "MissingContentLength")

    # Content-Length includes the multipart overhead (~220 bytes), as legacy.
    if storage_available < int(content_length):
        logger.error(
            "File upload failed because user's quota limit: quota(%d), used(%d), "
            "available(%s), filesize(%s)",
            account_record["quota"],
            storage_used,
            storage_available,
            content_length,
        )
        raise HTTPException(status_code=413, detail="Quota exceeded.")

    form = await request.form()
    file = next((value for value in form.values() if isinstance(value, StarletteUploadFile)), None)
    if file is None:
        raise InvalidInputError(
            "Expected a file part in the multipart request.", "MalformedRequest"
        )

    # Insert file metadata first so the file_uuid is available for the
    # destination filename. ``upload_url`` is stored verbatim for parity with
    # the legacy implementation. Guarded by the FILE_LIST lock so concurrent
    # uploads to the same dataset do not race on the file list update.
    _process_locks.lock(LockTypes.FILE_LIST)
    try:
        file_uuid = db.insert_file(
            name=file.filename,
            size=file.size or 0,
            is_link_only=0,
            upload_url=f"/article/{dataset_id}/upload",
            upload_token=token,
            dataset_uri=dataset["uri"],
            account_uuid=account_uuid,
        )
    finally:
        _process_locks.unlock(LockTypes.FILE_LIST)

    output_filename = os.path.join(config.storage, f"{dataset_id}_{file_uuid}")
    md5_hasher = hashlib.new("md5", usedforsecurity=False)
    file_size = 0
    is_incomplete: int | None = None

    try:
        # Use os.open + write so we can chmod the same descriptor afterwards,
        # matching the legacy's permission-tightening behaviour.
        destination_fd = os.open(output_filename, os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                if file_size + len(chunk) > storage_available:
                    is_incomplete = 1
                    break
                written = os.write(destination_fd, chunk)
                file_size += written
                md5_hasher.update(chunk)
            if os.name != "nt":
                os.fchmod(destination_fd, 0o400)
        finally:
            os.close(destination_fd)
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Writing {output_filename} to disk failed: {error}",
        ) from error

    computed_md5 = md5_hasher.hexdigest()

    # MD5 strict-check enforcement: clean up the partial upload then 400.
    if strict_check and computed_md5 != supplied_md5:
        try:
            from djehuty.utils.rdf import uuid_to_uri

            file_uri = uuid_to_uri(file_uuid, "file")
            if db.delete_item_from_list(dataset["uri"], "files", file_uri):
                db.cache.invalidate_by_prefix(f"{account_uuid}_storage")
                db.cache.invalidate_by_prefix(f"{dataset['uuid']}_dataset_storage")
        except (ImportError, KeyError, StopIteration):
            pass
        try:
            os.remove(output_filename)
        except OSError:
            pass
        raise InvalidInputError("MD5 checksum mismatch.", "MD5Mismatch")

    from djehuty.services.handles import register_file_handle
    from djehuty.services.imaging import image_mimetype

    download_url = f"{config.base_url}/file/{dataset_id}/{file_uuid}"

    # Only attempt thumbnail-eligibility detection on small images, matching
    # the legacy 10 MB ceiling.
    is_image = False
    if file_size < 10_000_001:
        is_image = image_mimetype(output_filename) is not None

    # Best-effort handle.net PID registration. Returns False (and the file
    # is marked with handle=None) if not configured.
    handle = None
    if not is_incomplete:
        handle = f"{config.handle_prefix}/{file_uuid}"
        if not register_file_handle(handle, download_url):
            handle = None

    db.update_file(
        account_uuid,
        file_uuid,
        dataset["uuid"],
        computed_md5=computed_md5,
        download_url=download_url,
        filesystem_location=output_filename,
        file_size=file_size,
        is_image=is_image,
        is_incomplete=is_incomplete,
        handle=handle,
    )

    response_data: dict[str, object] = {"location": f"{config.base_url}/v3/file/{file_uuid}"}
    if is_incomplete:
        response_data["is_incomplete"] = is_incomplete
    return JSONResponse(content=response_data)


# ---------------------------------------------------------------------------
# Dataset thumbnail
# ---------------------------------------------------------------------------


@router.put(
    "/datasets/{dataset_id}/update-thumbnail",
    summary="Set or clear the dataset thumbnail",
    responses={205: {"description": "Thumbnail updated"}, 403: {"model": ErrorResponse}},
)
def update_thumbnail(
    dataset_id: str,
    body: dict = Body(
        ...,
        openapi_examples={
            "set": {
                "summary": "Set thumbnail from an image file",
                "value": {"uuid": "9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8"},
            },
            "clear": {"summary": "Clear the thumbnail", "value": {"uuid": ""}},
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.services.imaging import generate_thumbnail
    from djehuty.services.storage import filesystem_location
    from djehuty.utils.convenience import value_or
    from djehuty.web import validator

    dataset = _resolve_dataset(db, dataset_id, account["uuid"])

    try:
        file_uuid = validator.string_value(body, "uuid", 0, 36, False)
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    # Empty UUID means "clear the thumbnail".
    if file_uuid == "" or file_uuid is None:
        if not db.dataset_update_thumb(
            dataset["uuid"],
            account["uuid"],
            file_uuid,
            None,
        ):
            raise InvalidInputError("Failed to clear thumbnail.", "ClearFailed")
        return Response(status_code=205)

    if not validator.is_valid_uuid(file_uuid):
        raise ForbiddenError("Invalid file UUID.")

    try:
        metadata = db.dataset_files(
            file_uuid=file_uuid,
            account_uuid=account["uuid"],
            limit=1,
        )[0]
    except (IndexError, AttributeError) as error:
        raise NotFoundError() from error

    if value_or(metadata, "size", 0) >= 10_000_000:
        raise InvalidInputError(
            "Cannot create thumbnails for images larger than 10MB.",
            "ImageTooLarge",
        )

    input_filename = filesystem_location(metadata)
    if input_filename is None:
        raise NotFoundError()

    extension = generate_thumbnail(input_filename, dataset["uuid"])
    if extension is None:
        raise InvalidInputError("Failed to generate thumbnail.", "ThumbnailFailed")

    if not db.dataset_update_thumb(
        dataset["uuid"],
        account["uuid"],
        file_uuid,
        extension,
    ):
        raise InvalidInputError("Failed to update thumbnail metadata.", "UpdateFailed")
    return Response(status_code=205)
