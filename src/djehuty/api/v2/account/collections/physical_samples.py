"""Authenticated /v2/account/collections physical sample endpoints."""

import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from rdflib import URIRef

from djehuty.api.dependencies import get_db, pagination_params, require_auth
from djehuty.api.exceptions import ForbiddenError, InvalidInputError, NotFoundError
from djehuty.api.services.physical_sample_service import PhysicalSampleService
from djehuty.api.v2.account.collections._shared import (
    _editable_collection,
    _resolve_private_collection,
)
from djehuty.web import formatter, validator

router = APIRouter(tags=["V2 / Account / Collections / Physical samples"])
_log = logging.getLogger(__name__)


@router.get(
    "/account/collections/{collection_id}/physical_samples",
    summary="List collection physical samples (private)",
)
def list_collection_physical_samples(
    collection_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
    paging: dict = Depends(pagination_params),
):
    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    samples = db.physical_samples(
        collection_uri=collection["uri"],
        is_latest=True,
        is_published=True,
        limit=paging["limit"],
        offset=paging["offset"],
    )
    return JSONResponse(
        content=[formatter.format_collection_physical_sample_record(r) for r in samples]
    )


@router.post(
    "/account/collections/{collection_id}/physical_samples",
    summary="Add physical samples to collection",
)
@router.put(
    "/account/collections/{collection_id}/physical_samples",
    summary="Replace collection physical samples",
)
def upsert_collection_physical_samples(
    request: Request,
    collection_id: str,
    body: dict,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    collection = _editable_collection(db, collection_id, account["uuid"])
    if collection is None:
        raise NotFoundError()

    existing = []
    if request.method == "POST":
        existing = [
            str(row["container_uri"]).removeprefix("container:")
            for row in db.collection_physical_sample_containers(collection["uri"], limit=None)
        ]

    service = PhysicalSampleService(db)
    try:
        container_uuids = list(dict.fromkeys(existing + body["samples"]))
        samples = []
        for index in range(len(container_uuids)):
            sample_uuid = validator.string_value(container_uuids, index, 36, 36)
            sample = service._resolve_physical_sample(
                sample_uuid, is_latest=True, is_published=True
            )
            if sample is None:
                return Response(status_code=500)
            samples.append(URIRef(f"container:{sample['container_uuid']}"))

        if db.update_item_list(collection["uuid"], account["uuid"], samples, "physical_samples"):
            db.cache.invalidate_by_prefix("physical-samples")
            return Response(status_code=205)
    except KeyError:
        raise InvalidInputError("Expected an array for 'samples'.", "NoSamplesField") from None
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error
    except (IndexError, TypeError):
        pass

    return Response(status_code=500)


@router.delete(
    "/account/collections/{collection_id}/physical_samples/{container_uuid}",
    summary="Remove physical sample from collection",
)
def delete_collection_physical_sample(
    collection_id: str, container_uuid: str, account=Depends(require_auth), db=Depends(get_db)
):
    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    sample = PhysicalSampleService(db)._resolve_physical_sample(
        container_uuid, is_latest=True, is_published=True
    )
    if sample is None:
        raise NotFoundError()

    container_uri = URIRef(f"container:{sample['container_uuid']}")
    if db.delete_item_from_list(collection["uri"], "physical_samples", container_uri):
        db.cache.invalidate_by_prefix("physical-samples")
        return Response(status_code=204)

    _log.error(
        "account:%s failed to remove physical sample:%s from collection:%s.",
        account["uuid"],
        container_uuid,
        collection_id,
    )
    raise ForbiddenError()
