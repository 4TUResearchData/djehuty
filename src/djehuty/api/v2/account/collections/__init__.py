"""Authenticated /v2/account/collections endpoints, grouped by sub-resource."""

from fastapi import APIRouter

from djehuty.api.v2.account.collections import (
    articles,
    authors,
    categories,
    collections,
    funding,
    physical_samples,
    publishing,
)

router = APIRouter()
for _m in (
    collections,
    authors,
    categories,
    articles,
    physical_samples,
    funding,
    publishing,
):
    router.include_router(_m.router)
