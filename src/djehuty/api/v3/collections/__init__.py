"""Authenticated /v3/collections endpoints, grouped by sub-resource."""

from fastapi import APIRouter

from djehuty.api.v3.collections import publishing, references, tags

router = APIRouter()
for _m in (publishing, references, tags):
    router.include_router(_m.router)
