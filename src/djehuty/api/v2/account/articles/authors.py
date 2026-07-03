"""Authenticated /v2/account/articles authors endpoints."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.v2.account.articles._shared import _ok, _resolve_private_dataset
from djehuty.web import formatter

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
    dataset_id: str, body: dict, account=Depends(require_auth), db=Depends(get_db)
):
    from djehuty.utils.rdf import uris_from_records

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    input_authors = body.get("authors", [])

    new_author_uuids = []
    for author_data in input_authors:
        if "uuid" in author_data and author_data["uuid"]:
            new_author_uuids.append(author_data["uuid"])
        else:
            author_uuid = db.insert_author(
                first_name=author_data.get("first_name", ""),
                last_name=author_data.get("last_name", ""),
                full_name=author_data.get("name")
                or f"{author_data.get('first_name', '')} {author_data.get('last_name', '')}".strip(),
                email=author_data.get("email"),
                orcid_id=author_data.get("orcid_id"),
            )
            if author_uuid:
                new_author_uuids.append(author_uuid)

    existing = db.authors(
        item_uri=dataset["uri"],
        item_type="dataset",
        account_uuid=account["uuid"],
        is_published=False,
        limit=10000,
    )
    existing_uuids = [a["uuid"] for a in existing if "uuid" in a]

    combined = existing_uuids + [u for u in new_author_uuids if u not in existing_uuids]
    combined_records = [{"uuid": u} for u in combined]
    uris = uris_from_records(combined_records, "author", "uuid")
    db.update_item_list(dataset["uuid"], account["uuid"], uris, "authors")
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
    uris = uris_from_records(remaining, "author", "uuid")
    db.update_item_list(dataset["uuid"], account["uuid"], uris, "authors")
    return Response(status_code=204)
