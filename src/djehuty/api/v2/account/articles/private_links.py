"""Authenticated /v2/account/articles private_links endpoints."""

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db, require_auth
from djehuty.api.exceptions import NotFoundError
from djehuty.api.v2.account.articles._shared import _ok, _resolve_private_dataset
from djehuty.web import formatter
from djehuty.web.config import config

router = APIRouter(prefix="/account", tags=["V2 / Account / Articles / Links"])


_PRIVATE_LINK_EXAMPLE = {
    "id": "8G2fkfIJP0",
    "is_active": True,
    "expires_date": "2032-01-01T00:00:00",
}


@router.get(
    "/articles/{dataset_id}/private_links",
    summary="List private links",
    responses={200: _ok("List of private links", [_PRIVATE_LINK_EXAMPLE])},
)
def list_private_links(dataset_id: str, account=Depends(require_auth), db=Depends(get_db)):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    links = db.private_links(item_uri=dataset["uri"], account_uuid=account["uuid"])
    return JSONResponse(content=[formatter.format_private_links_record(link) for link in links])


@router.post(
    "/articles/{dataset_id}/private_links",
    summary="Create a private link",
    responses={
        200: _ok(
            "Private link created",
            {"location": "https://data.4tu.nl/private_datasets/8G2fkfIJP0"},
        )
    },
)
def create_private_link(
    dataset_id: str,
    body: dict = Body(
        default={},
        openapi_examples={
            "with_expiry": {
                "summary": "Link that expires",
                "value": {"expires_date": "2032-01-01", "read_only": False},
            },
        },
    ),
    account=Depends(require_auth),
    db=Depends(get_db),
):
    import secrets

    from djehuty.web import validator

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])

    expires_date = validator.date_value(body, "expires_date", False) if body else None
    if expires_date:
        expires_date = f"{expires_date}T00:00:00Z"
    read_only = validator.boolean_value(body, "read_only", False) if body else None
    id_string = secrets.token_urlsafe()

    # insert_private_link handles both creating the link and updating the item list
    db.insert_private_link(
        dataset["uuid"],
        account["uuid"],
        item_type="dataset",
        expires_date=expires_date,
        read_only=read_only,
        id_string=id_string,
        is_active=True,
    )

    return JSONResponse(content={"location": f"{config.base_url}/private_datasets/{id_string}"})


@router.get(
    "/articles/{dataset_id}/private_links/{link_id}",
    summary="Get private link",
)
def get_private_link(
    dataset_id: str, link_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    links = db.private_links(
        item_uri=dataset["uri"], id_string=link_id, account_uuid=account["uuid"]
    )
    if not links:
        raise NotFoundError()
    return JSONResponse(content=[formatter.format_private_links_record(link) for link in links])


@router.put(
    "/articles/{dataset_id}/private_links/{link_id}",
    summary="Update private link",
)
def update_private_link(
    dataset_id: str, link_id: str, body: dict, account=Depends(require_auth), db=Depends(get_db)
):
    from djehuty.web import validator

    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    expires_date = validator.string_value(body, "expires_date", 0, 255, False) if body else None
    is_active = validator.boolean_value(body, "is_active", False) if body else None
    db.update_private_link(
        dataset["uri"], account["uuid"], link_id, expires_date=expires_date, is_active=is_active
    )
    return JSONResponse(content={"location": f"{config.base_url}/private_datasets/{link_id}"})


@router.delete(
    "/articles/{dataset_id}/private_links/{link_id}",
    summary="Delete a private link",
)
def delete_private_link(
    dataset_id: str, link_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    dataset = _resolve_private_dataset(db, dataset_id, account["uuid"])
    db.delete_private_links(dataset["container_uuid"], account["uuid"], link_id)
    return Response(status_code=204)
