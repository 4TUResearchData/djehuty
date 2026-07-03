"""Single-file metadata endpoints for the v3 API."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.permissions import enforce_collaborative_permissions
from djehuty.api.v3._shared import _ok
from djehuty.web import formatter
from djehuty.web.config import config

router = APIRouter(tags=["V3 / Files"])

_FILE_DETAILS_EXAMPLE = {
    "status": None,
    "viewer_type": None,
    "preview_state": None,
    "upload_url": None,
    "upload_token": None,
    "uuid": "9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8",
    "id": None,
    "name": "measurements.csv",
    "size": 248193,
    "is_link_only": False,
    "download_url": "https://data.4tu.nl/file/27e6a01d-3f09-4d90-ae02-1d749ae9efb8/9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8",
    "supplied_md5": "0cc175b9c0f1b6a831c399e269772661",
    "computed_md5": "0cc175b9c0f1b6a831c399e269772661",
}


@router.get(
    "/file/{file_id}",
    summary="Get file details by id",
    responses={200: _ok("File metadata", _FILE_DETAILS_EXAMPLE), 403: {"model": ErrorResponse}},
)
def get_file_details(
    file_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    account_uuid = account["uuid"]
    try:
        records = db.dataset_files(
            file_uuid=file_id,
            account_uuid=account_uuid,
            limit=1,
        )
        metadata = records[0]
    except (IndexError, AttributeError, TypeError) as error:
        raise NotFoundError() from error
    # AS-IS: a collaborator needs data_read on the file; owners no-op.
    enforce_collaborative_permissions(db, account_uuid, metadata, "file", "data_read")
    try:
        metadata["base_url"] = config.base_url
        return JSONResponse(content=formatter.format_file_details_record(metadata))
    except KeyError as error:
        raise NotFoundError() from error
