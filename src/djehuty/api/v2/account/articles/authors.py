"""Authenticated /v2/account/articles authors endpoints."""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.services.request_lists import author_list_from_request_input
from djehuty.api.v2.account.articles._shared import _ok, _resolve_private_dataset
from djehuty.web import formatter, validator

router = APIRouter(prefix="/account", tags=["V2 / Account / Articles / Authors"])


_AUTHOR_EXAMPLE = {
    "id": None,
    "uuid": "08f4d496-67b5-4b7c-b2d2-923458d1f450",
    "full_name": "John Doe",
    "is_active": False,
    "url_name": None,
    "orcid_id": "",
}


@router.get(
    "/articles/{dataset_id}/authors",
    summary="List article authors",
    responses={200: _ok("List of authors", [_AUTHOR_EXAMPLE])},
)
def list_article_authors(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    authors = db.authors(
        item_uri=dataset["uri"],
        item_type="dataset",
        account_uuid=account["uuid"],
        is_published=False,
        limit=10000,
    )
    return JSONResponse(content=[formatter.format_author_record(a) for a in authors])


@router.post(
    "/articles/{dataset_id}/authors",
    summary="Add authors to dataset",
)
@router.put(
    "/articles/{dataset_id}/authors",
    summary="Replace dataset authors",
)
def upsert_article_authors(
    dataset_id: str,
    body: dict,
    request: Request,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from djehuty.utils.rdf import uris_from_records

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])

    try:
        new_authors, errors = author_list_from_request_input(body, db, account["uuid"])
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    if errors:
        raise InvalidInputError(errors, "BadAuthorsInput")

    existing_authors = []
    if request.method == "POST":
        existing = db.authors(
            item_uri=dataset["uri"],
            item_type="dataset",
            account_uuid=account["uuid"],
            is_published=False,
            limit=10000,
        )
        existing_authors = uris_from_records(
            [a for a in existing if "uuid" in a],
            "author",
            "uuid",
        )

    authors = list(dict.fromkeys(existing_authors + new_authors))
    db.update_item_list(dataset["uuid"], account["uuid"], authors, "authors")
    return Response(status_code=205)


@router.delete(
    "/articles/{dataset_id}/authors/{author_id}",
    summary="Remove an author",
)
def delete_article_author(
    dataset_id: str, author_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    from djehuty.utils.rdf import uris_from_records

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    authors = db.authors(
        item_uri=dataset["uri"],
        item_type="dataset",
        account_uuid=account["uuid"],
        is_published=False,
        limit=10000,
    )

    remaining = [
        a for a in authors if str(a.get("id")) != str(author_id) and a.get("uuid") != author_id
    ]
    # AS-IS: legacy raises StopIteration on a missing author -> HTTP 500.
    if len(remaining) == len(authors):
        return Response(status_code=500)
    uris = uris_from_records(remaining, "author", "uuid")
    db.update_item_list(dataset["uuid"], account["uuid"], uris, "authors")
    return Response(status_code=204)
