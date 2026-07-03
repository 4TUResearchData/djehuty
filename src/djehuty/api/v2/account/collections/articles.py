"""Authenticated /v2/account/collections articles endpoints."""

import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from rdflib import URIRef

from djehuty.api.dependencies import get_db, pagination_params, require_auth
from djehuty.api.exceptions import ForbiddenError, InvalidInputError, NotFoundError
from djehuty.api.services.article_service import ArticleService
from djehuty.api.v2.account.collections._shared import (
    _find_collection,
    _resolve_private_collection,
)
from djehuty.utils.convenience import parses_to_int
from djehuty.web import formatter, validator
from djehuty.web.config import config

router = APIRouter(tags=["V2 / Account / Collections / Articles"])
_log = logging.getLogger(__name__)


@router.get(
    "/account/collections/{collection_id}/articles",
    summary="List collection articles (private)",
)
def list_private_collection_articles(
    collection_id: str,
    account=Depends(require_auth),
    db=Depends(get_db),
    paging: dict = Depends(pagination_params),
):
    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    datasets = db.datasets(
        collection_uri=collection["uri"],
        is_latest=True,
        limit=paging["limit"],
        offset=paging["offset"],
    )
    return JSONResponse(
        content=[
            formatter.format_dataset_record({**r, "base_url": config.base_url}) for r in datasets
        ]
    )


@router.post(
    "/account/collections/{collection_id}/articles",
    summary="Add articles to collection",
)
@router.put(
    "/account/collections/{collection_id}/articles",
    summary="Replace collection articles",
)
def upsert_collection_articles(
    request: Request,
    collection_id: str,
    body: dict,
    account=Depends(require_auth),
    db=Depends(get_db),
):
    collection = _find_collection(db, collection_id, account["uuid"], is_published=False)
    if collection is None:
        published = _find_collection(db, collection_id, account["uuid"], is_published=True)
        if published is None:
            raise NotFoundError()
        draft_uuid = db.create_draft_from_published_collection(published["container_uuid"])
        if draft_uuid is None:
            raise NotFoundError()
        collection = _find_collection(
            db, published["container_uuid"], account["uuid"], is_published=False
        )
        if collection is None:
            raise NotFoundError()

    existing_datasets = []
    if request.method == "POST":
        records = db.datasets(collection_uri=collection["uri"], is_latest=True, limit=10000)
        if records:
            existing_datasets = [record["container_uuid"] for record in records]

    service = ArticleService(db)
    try:
        datasets = existing_datasets + body["articles"]
        for index, _ in enumerate(datasets):
            if parses_to_int(datasets[index]):
                dataset_id = validator.integer_value(datasets, index)
            else:
                dataset_id = validator.string_value(datasets, index, 36, 36)

            dataset = service._resolve_dataset(dataset_id, is_latest=True, is_published=True)
            if dataset is None:
                return Response(status_code=500)
            datasets[index] = URIRef(dataset["container_uri"])

        if db.update_item_list(collection["uuid"], account["uuid"], datasets, "datasets"):
            db.cache.invalidate_by_prefix("datasets")
            return Response(status_code=205)
    except KeyError:
        raise InvalidInputError("Expected an array for 'articles'.", "NoArticlesField")
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code)
    except (IndexError, TypeError):
        pass

    return Response(status_code=500)


@router.delete(
    "/account/collections/{collection_id}/articles/{article_id}",
    summary="Remove article from collection",
)
def delete_collection_article(
    collection_id: str, article_id: str, account=Depends(require_auth), db=Depends(get_db)
):
    collection = _resolve_private_collection(db, collection_id, account["uuid"])
    dataset = ArticleService(db)._resolve_dataset(article_id)
    if dataset is None:
        raise NotFoundError()

    if db.delete_item_from_list(collection["uri"], "datasets", dataset["container_uri"]):
        db.cache.invalidate_by_prefix("datasets")
        return Response(status_code=204)

    _log.error(
        "account:%s failed to remove dataset:%s from collection:%s.",
        account["uuid"],
        article_id,
        collection_id,
    )
    raise ForbiddenError()
