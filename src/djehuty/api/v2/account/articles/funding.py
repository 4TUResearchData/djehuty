"""Authenticated /v2/account/articles funding endpoints."""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import InvalidInputError
from djehuty.api.v2.account.articles._shared import _ok, _resolve_private_dataset
from djehuty.web import formatter

router = APIRouter(prefix="/account", tags=["V2 / Account / Articles / Funding"])


_FUNDING_EXAMPLE = {
    "id": None,
    "uuid": "6f605fe1-e87a-43f5-8b67-70ebe3f9b868",
    "title": "Example cases fund",
    "grant_code": "EXA-001",
    "funder_name": "Example",
    "is_user_defined": None,
    "url": "https://example.exa",
}


def _funding_list_from_request_input(parameters, db, created_by=None):
    """Parse a funding-records body into a list of funding URIs.

    Mirrors ``djehuty.web.wsgi.__funding_list_from_request_input``: accepts
    either a ``funding_list`` or ``funders`` key, each entry being either
    ``{"uuid": "<funder-uuid>"}`` to reference an existing funder, or
    ``{"title", "grant_code", "funder_name", "url"}`` to create a new one
    via :meth:`db.insert_funding`.

    Returns ``(uri_list, errors)``.
    """
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri
    from djehuty.web import validator

    errors = []
    records = validator.array_value(parameters, "funding_list", error_list=errors)
    if not records and not errors:
        records = validator.array_value(parameters, "funders", error_list=errors)

    if errors:
        return None, errors
    if records is None:
        return [], None

    funding_items = []
    for record in records:
        funder_uuid = validator.string_value(record, "uuid", 0, 36, False)
        if funder_uuid and not validator.is_valid_uuid(funder_uuid):
            return None, [
                {
                    "field_name": "funding_list.uuid",
                    "message": "Invalid UUID for funder.",
                }
            ]

        if funder_uuid:
            funding_items.append(URIRef(uuid_to_uri(funder_uuid, "funding")))
            continue

        new_funder = {
            "title": validator.string_value(record, "title", 0, 255, True),
            "grant_code": validator.string_value(record, "grant_code", 0, 32, False),
            "funder_name": validator.string_value(record, "funder_name", 0, 255, False),
            "url": validator.string_value(record, "url", 0, 512, False),
            "account_uuid": created_by,
        }
        funder_uuid = db.insert_funding(**new_funder)
        if funder_uuid is None:
            return None, [
                {
                    "field_name": "funding_list.uuid",
                    "message": "Unable to create funding record.",
                }
            ]
        funding_items.append(URIRef(uuid_to_uri(funder_uuid, "funding")))

    return funding_items, None


@router.get(
    "/articles/{dataset_id}/funding",
    summary="List funding",
    responses={200: _ok("List of funding", [_FUNDING_EXAMPLE])},
)
def list_article_funding(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    fundings = db.fundings(
        item_uri=dataset["uri"],
        item_type="dataset",
        account_uuid=account["uuid"],
        is_published=False,
    )
    return JSONResponse(content=[formatter.format_funding_record(f) for f in fundings])


@router.post(
    "/articles/{dataset_id}/funding",
    summary="Add funding records (appends)",
)
@router.put(
    "/articles/{dataset_id}/funding",
    summary="Replace funding records",
)
def upsert_article_funding(
    dataset_id: str,
    body: dict,
    request: Request,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    new_fundings, errors = _funding_list_from_request_input(body, db, account["uuid"])
    if errors:
        raise InvalidInputError(errors, "BadFundingInput")

    # POST appends to existing funding; PUT replaces.
    existing = []
    if request.method == "POST":
        existing_records = db.fundings(
            item_uri=dataset["uri"],
            account_uuid=account["uuid"],
            item_type="dataset",
            is_published=False,
            limit=10000,
        )
        existing = [URIRef(uuid_to_uri(rec["uuid"], "funding")) for rec in existing_records]

    if not db.update_item_list(
        dataset["uuid"],
        account["uuid"],
        existing + new_fundings,
        "funding_list",
    ):
        raise InvalidInputError("Adding a single funder failed.", "FundingUpdateFailed")
    return Response(status_code=205)


@router.delete(
    "/articles/{dataset_id}/funding/{funding_id}",
    summary="Remove funding",
)
def delete_article_funding(
    dataset_id: str, funding_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    from djehuty.utils.rdf import uris_from_records

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    fundings = db.fundings(
        item_uri=dataset["uri"],
        item_type="dataset",
        account_uuid=account["uuid"],
        is_published=False,
        limit=10000,
    )
    remaining = [f for f in fundings if f.get("uuid") != funding_id]
    uris = uris_from_records(remaining, "funding", "uuid")
    db.update_item_list(dataset["uuid"], account["uuid"], uris, "funding_list")
    return Response(status_code=204)
