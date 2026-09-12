"""RO-Crate metadata endpoints for the v3 API."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db
from djehuty.api.exceptions import NotFoundError
from djehuty.api.v3._shared import _ok
from djehuty.services.git import repository_url_for_dataset
from djehuty.web import formatter
from djehuty.web.config import config

router = APIRouter(tags=["V3 / RO-Crates"])

_ROCRATE_EXAMPLE = {
    "@context": "https://w3id.org/ro/crate/1.1/context",
    "@graph": [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            "about": {"@id": "./"},
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "identifier": "https://doi.org/10.4121/27e6a01d-3f09-4d90-ae02-1d749ae9efb8.v1",
            "datePublished": "2026-07-03T10:48:50",
            "name": "Coastal water temperature measurements",
            "description": "Hourly measurements collected in 2025.",
            "keywords": ["climate", "oceanography"],
            "license": {"@id": "https://spdx.org/licenses/CC-BY-4.0"},
            "author": [{"@type": "Person", "givenName": "Ada", "familyName": "Lovelace"}],
            "hasPart": [{"@id": "9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8"}],
        },
        {
            "@id": "9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8",
            "@type": "File",
            "name": "measurements.csv",
            "contentSize": "248193",
            "contentUrl": "https://data.4tu.nl/file/27e6a01d-3f09-4d90-ae02-1d749ae9efb8/9b1c3f2a-4d5e-6f70-8192-a3b4c5d6e7f8",
        },
    ],
}


@router.get(
    "/ro-crates",
    summary="List RO-Crate enabled datasets",
    responses={200: _ok("RO-Crate records", [_ROCRATE_EXAMPLE])},
)
def list_ro_crates(
    db=Depends(get_db),
    page: str | None = Query(None),
    page_size: str | None = Query(None),
    limit: str | None = Query(None),
    offset: str | None = Query(None),
    modified_since: str | None = Query(None, max_length=32),
    order: str | None = Query(None, max_length=255),
    order_direction: str | None = Query(None, max_length=8),
):
    from djehuty.web import validator

    # AS-IS (#111): two legacy bugs reproduced here.
    #  1. paging_to_offset_and_limit() calls integer_value() WITHOUT forwarding
    #     error_list, so an invalid `limit` RAISES InvalidIntegerValue instead
    #     of returning a 400; the legacy handler doesn't wrap the paging call in
    #     a try, so it propagates -> HTTP 500. (Hence `limit` is taken as a raw
    #     string here, not coerced/validated by FastAPI.)
    #  2. format_rocrate_record() subscripts record['doi'] unguarded
    #     (KeyError -> uncaught -> HTTP 500) for datasets without a DOI.
    errors: list = []
    offset_v, limit_v = validator.paging_to_offset_and_limit(
        {"page": page, "page_size": page_size, "limit": limit, "offset": offset},
        error_list=errors,
    )

    datasets = db.datasets(
        is_published=True,
        is_latest=True,
        is_embargoed=False,
        is_restricted=False,
        modified_since=modified_since,
        order=order,
        order_direction=order_direction,
        limit=limit_v,
        offset=offset_v,
    )
    output = []
    for dataset in datasets:
        output.append(
            formatter.format_rocrate_record(
                config.base_url,
                config.site_name,
                dataset,
                config.publisher_rors.get(config.site_name),
                tags=db.tags(item_uri=dataset["uri"], limit=None),
                authors=db.authors(
                    item_uri=dataset["uri"], is_published=True, item_type="dataset", limit=10000
                ),
                files=db.dataset_files(dataset_uri=dataset["uri"]),
                git_url=repository_url_for_dataset(dataset),
            )
        )
    return JSONResponse(content=output)


def _ro_crate_record(db, identifier, version=None):
    """Resolve the dataset and format its RO-Crate record as legacy does."""
    from djehuty.utils.convenience import parses_to_int
    from djehuty.web import validator

    if version is not None and not parses_to_int(version):
        raise NotFoundError()

    parameters = {
        "is_published": True,
        "is_latest": False,
        "version": version,
        "limit": 1,
    }
    dataset = None
    try:
        if parses_to_int(identifier):
            dataset = db.datasets(dataset_id=int(identifier), **parameters)[0]
        elif validator.is_valid_uuid(identifier):
            dataset = db.datasets(container_uuid=identifier, **parameters)[0]
    except IndexError:
        dataset = None
    if dataset is None:
        raise NotFoundError()

    return formatter.format_rocrate_record(
        config.base_url,
        config.site_name,
        dataset,
        config.publisher_rors.get(config.site_name),
        tags=db.tags(item_uri=dataset["uri"], limit=None),
        authors=db.authors(
            item_uri=dataset["uri"], is_published=True, item_type="dataset", limit=10000
        ),
        files=db.dataset_files(dataset_uri=dataset["uri"]),
        git_url=repository_url_for_dataset(dataset),
    )


@router.get(
    "/datasets/{container_uuid}/ro-crate-metadata.json",
    summary="Get RO-Crate metadata for a dataset",
    responses={200: _ok("RO-Crate metadata document", _ROCRATE_EXAMPLE)},
)
def get_ro_crate_metadata(container_uuid: str, db=Depends(get_db)):
    return JSONResponse(content=_ro_crate_record(db, container_uuid))


@router.get(
    "/datasets/{container_uuid}/versions/{version}/ro-crate-metadata.json",
    summary="Get RO-Crate metadata for a specific dataset version",
    responses={200: _ok("RO-Crate metadata document", _ROCRATE_EXAMPLE)},
)
def get_versioned_ro_crate_metadata(
    container_uuid: str,
    version: int,
    db=Depends(get_db),
):
    return JSONResponse(content=_ro_crate_record(db, container_uuid, version=version))
