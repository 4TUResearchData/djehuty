"""Public and authenticated /v3/datasets endpoints, grouped by sub-resource."""

from fastapi import APIRouter

from djehuty.api.v3.datasets import (
    authors,
    badges,
    collaborators,
    files,
    listing,
    publishing,
    references,
    tags,
)

router = APIRouter()
for _m in (listing, publishing, references, tags, files, authors, collaborators, badges):
    router.include_router(_m.router)
