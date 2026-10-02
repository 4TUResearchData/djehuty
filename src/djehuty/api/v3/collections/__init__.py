"""Authenticated /v3/collections endpoints, grouped by sub-resource."""

from fastapi import APIRouter

from djehuty.api.v3.collections import physical_samples, publishing, references, tags

router = APIRouter()
for _m in (publishing, references, tags, physical_samples):
    router.include_router(_m.router)
