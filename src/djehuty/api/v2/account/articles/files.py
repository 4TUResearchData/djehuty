"""Authenticated /v2/account/articles files endpoints."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, get_token, require_auth
from djehuty.api.exceptions import ForbiddenError, InvalidInputError, NotFoundError
from djehuty.api.services.article_service import ArticleService
from djehuty.api.v2.account.articles._shared import _ok, _resolve_private_dataset
from djehuty.web import formatter
from djehuty.web.config import config

router = APIRouter(prefix="/account", tags=["V2 / Account / Articles / Files"])


_FILE_EXAMPLE = {
    "id": None,
    "uuid": "d112d0cd-bc15-4f8e-9013-930750fc017a",
    "name": "README.md",
    "size": 3696,
    "is_link_only": False,
    "is_incomplete": False,
    "download_url": "https://data.4tu.nl/file/d7b3daa5-45e2-47b0-9910-0f7fa6a995b1/d112d0cd-bc15-4f8e-9013-930750fc017a",
    "supplied_md5": None,
    "computed_md5": "c5b36584a0d62d28e9bf9e6892d9ebac",
}


@router.get(
    "/articles/{dataset_id}/files",
    summary="List article files",
    responses={200: _ok("List of files", [_FILE_EXAMPLE])},
)
def list_private_article_files(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    files = db.dataset_files(dataset_uri=dataset["uri"], account_uuid=account["uuid"])
    return JSONResponse(
        content=[
            formatter.format_file_for_dataset_record({**f, "base_url": config.base_url})
            for f in files
        ]
    )


@router.get(
    "/articles/{dataset_id}/files/{file_id}",
    summary="Get file details",
    responses={200: _ok("File details", _FILE_EXAMPLE)},
)
def get_private_article_file(
    dataset_id: str, file_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    files = db.dataset_files(
        dataset_uri=dataset["uri"], file_uuid=file_id, account_uuid=account["uuid"]
    )
    if not files:
        raise NotFoundError()
    return JSONResponse(
        content=formatter.format_file_details_record({**files[0], "base_url": config.base_url})
    )


@router.post(
    "/articles/{dataset_id}/files",
    summary="Register a file or link",
)
def create_article_file(
    dataset_id: str,
    body: dict,
    account=Depends(require_auth),
    db=Depends(get_db),
    token: str | None = Depends(get_token),
):
    from djehuty.web import validator

    try:
        link = validator.string_value(body, "link", 0, 1000, False)
        dataset = ArticleService(db)._resolve_dataset(
            dataset_id, account_uuid=account["uuid"], is_published=False
        )
        if dataset is None:
            raise ForbiddenError()

        if link is not None:
            file_id = db.insert_file(
                dataset_uri=dataset["uri"],
                account_uuid=account["uuid"],
                is_link_only=True,
                download_url=link,
            )
        else:
            file_id = db.insert_file(
                dataset_uri=dataset["uri"],
                account_uuid=account["uuid"],
                is_link_only=False,
                upload_token=token,
                supplied_md5=validator.string_value(body, "md5", 32, 32),
                name=validator.string_value(body, "name", 0, 255, True),
                size=validator.integer_value(body, "size", 0, pow(2, 63), True),
            )

        if file_id is None:
            return Response(status_code=500)

        return JSONResponse(
            status_code=201,
            content={
                "location": f"{config.base_url}/v2/account/articles/{dataset_id}/files/{file_id}"
            },
        )
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error


@router.delete(
    "/articles/{dataset_id}/files",
    summary="Remove all files",
)
def delete_all_article_files(
    dataset_id: str, body: dict, account=Depends(require_auth), db=Depends(get_db)
):
    from djehuty.web import validator

    try:
        remove_all = validator.boolean_value(body, "remove_all", when_none=False)
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error
    if remove_all is False:
        raise InvalidInputError("Expected a 'remove_all' field.", "400")

    service = ArticleService(db)
    dataset = service._resolve_dataset(dataset_id, account_uuid=account["uuid"], is_published=False)
    if dataset is None:
        raise ForbiddenError()

    if db.delete_items_all_from_list(dataset["uri"], "files"):
        db.cache.invalidate_by_prefix(f"{account['uuid']}_storage")
        db.cache.invalidate_by_prefix(f"{dataset['uuid']}_dataset_storage")
        return Response(status_code=204)
    return Response(status_code=500)


@router.delete(
    "/articles/{dataset_id}/files/{file_id}",
    summary="Delete a file",
)
def delete_private_article_file(
    dataset_id: str, file_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    db.delete_item_from_list(dataset["uri"], "files", URIRef(uuid_to_uri(file_id, "file")))
    db.cache.invalidate_by_prefix(f"{account['uuid']}_storage")
    db.cache.invalidate_by_prefix(f"{dataset['uuid']}_dataset_storage")
    return Response(status_code=204)
