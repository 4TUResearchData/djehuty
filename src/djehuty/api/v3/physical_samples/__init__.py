"""Public and authenticated /v3/physical-samples (IGSN) endpoints, grouped by sub-resource."""

from fastapi import APIRouter

from djehuty.api.v3.physical_samples import (
    categories,
    creators,
    dates,
    listing,
    private_links,
    publishing,
    related_resources,
    tags,
)

router = APIRouter()
for _m in (
    listing,
    publishing,
    creators,
    dates,
    related_resources,
    tags,
    categories,
    private_links,
):
    router.include_router(_m.router)
