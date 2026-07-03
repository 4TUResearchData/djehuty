"""Public /v2/licenses endpoint."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db
from djehuty.api.models.licenses import License
from djehuty.web import formatter

router = APIRouter(tags=["V2 / Licenses"])


@router.get(
    "/licenses",
    response_model=list[License],
    summary="List all available licenses",
    description="Returns all licenses that can be applied to datasets and collections.",
    responses={
        200: {
            "description": "List of licenses",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "value": 1,
                            "name": "CC BY 4.0",
                            "url": "https://creativecommons.org/licenses/by/4.0/",
                            "type": "data",
                        },
                        {
                            "value": 2,
                            "name": "CC0 1.0",
                            "url": "https://creativecommons.org/publicdomain/zero/1.0/",
                            "type": "data",
                        },
                    ]
                }
            },
        }
    },
)
def list_licenses(db=Depends(get_db)):
    records = db.licenses()
    return JSONResponse(content=[formatter.format_license_record(r) for r in records])
