"""Public physical sample endpoints for the v2 API."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db
from djehuty.api.exceptions import InvalidInputError
from djehuty.web import formatter, validator

router = APIRouter(tags=["V2 / Physical samples"])


@router.post("/physical_samples/search", summary="Search published physical samples")
def search_physical_samples(body: dict, db=Depends(get_db)):
    try:
        search_for = validator.string_value(body, "search_for", 1, 1024, required=True)
    except validator.ValidationException as error:
        raise InvalidInputError(error.message, error.code) from error

    samples = db.physical_samples(
        search_for=search_for, is_published=True, is_latest=True, limit=20, use_cache=False
    )
    return JSONResponse(
        content=[formatter.format_collection_physical_sample_record(r) for r in samples]
    )
