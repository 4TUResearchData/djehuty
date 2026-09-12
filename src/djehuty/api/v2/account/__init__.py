"""Authenticated /v2/account endpoints, grouped by resource."""

from fastapi import APIRouter

from djehuty.api.v2.account import (
    account,
    articles,
    authors,
    collections,
    funding,
    institutions,
    oauth,
)

# Include order sets the group order in the docs: Account, then its leaf
# resources, then the larger articles/collections trees.
router = APIRouter()
for _module in (account, authors, funding, institutions, articles, collections, oauth):
    router.include_router(_module.router)
