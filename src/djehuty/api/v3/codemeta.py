"""Codemeta endpoints for the v3 API."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db
from djehuty.api.v3._shared import _ok
from djehuty.services.git import repository_url_for_dataset
from djehuty.web import formatter
from djehuty.web.config import config

router = APIRouter(tags=["V3 / Codemeta"])

_CODEMETA_EXAMPLE = [
    {
        "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
        "@type": "SoftwareSourceCode",
        "name": "Wave model toolkit",
        "license": "https://spdx.org/licenses/MIT",
        "dateCreated": "2026-01-12T09:00:00",
        "datePublished": "2026-02-01T09:00:00",
        "dateModified": "2026-02-01T09:00:00",
        "identifier": "10.4121/12345678-abcd-1234.v1",
        "description": ["Wave model toolkit", "A toolkit for coastal wave modelling."],
        "keywords": ["oceanography", "modelling"],
        "author": [{"@type": "Person", "givenName": "Ada", "familyName": "Lovelace"}],
        "referencePublication": [],
        "version": 1,
    }
]


@router.get(
    "/codemeta",
    summary="List published software in codemeta format",
    responses={200: _ok("Published software as CodeMeta records", _CODEMETA_EXAMPLE)},
)
def list_codemeta(
    db=Depends(get_db),
    limit: int | None = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    order: str | None = Query(None, max_length=255),
    order_direction: str | None = Query(None, pattern="^(asc|desc)$"),
    modified_since: str | None = Query(None, max_length=32),
    doi: str | None = Query(None, max_length=255),
):
    datasets = db.datasets(
        is_published=True,
        is_latest=True,
        is_software=True,
        is_embargoed=False,
        is_restricted=False,
        doi=doi,
        modified_since=modified_since,
        order=order,
        order_direction=order_direction,
        limit=limit,
        offset=offset,
    )
    output = []
    for dataset in datasets:
        has_files = bool(db.dataset_files(dataset_uri=dataset["uri"], limit=1))
        output.append(
            formatter.format_codemeta_record(
                dataset,
                git_url=repository_url_for_dataset(dataset),
                tags=db.tags(item_uri=dataset["uri"], limit=None),
                authors=db.authors(
                    item_uri=dataset["uri"],
                    is_published=True,
                    item_type="dataset",
                    limit=10000,
                ),
                has_files=has_files,
                base_url=config.base_url,
            )
        )
    return JSONResponse(content=output)
