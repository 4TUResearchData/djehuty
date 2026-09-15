"""Public /v2/categories endpoint."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import get_db
from djehuty.api.models.categories import Category
from djehuty.web import formatter

router = APIRouter(tags=["V2 / Categories"])


@router.get(
    "/categories",
    response_model=list[Category],
    summary="List all research categories",
    description=(
        "Returns the full category taxonomy used for classifying datasets and "
        "collections. Categories are hierarchical; use `parent_id` to build a tree."
    ),
    responses={
        200: {
            "description": "List of categories",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 13622,
                            "uuid": "01fddd41-68d2-4e28-9d9c-18347847e7d1",
                            "title": "Mining and Extraction of Energy Resources",
                            "parent_id": 13620,
                            "parent_uuid": "6e5bdc69-96db-41e4-ac0b-18812b46c49c",
                        },
                    ]
                }
            },
        }
    },
)
def list_categories(db=Depends(get_db)):
    records = db.categories(limit=None)
    return JSONResponse(content=[formatter.format_category_record(r) for r in records])
