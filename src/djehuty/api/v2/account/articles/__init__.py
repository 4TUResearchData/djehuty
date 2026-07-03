"""Authenticated /v2/account/articles endpoints, grouped by sub-resource."""

from fastapi import APIRouter

from djehuty.api.v2.account.articles import (
    articles,
    authors,
    categories,
    embargo,
    files,
    funding,
    private_links,
    publishing,
)

router = APIRouter()
for _m in (articles, authors, categories, files, embargo, private_links, funding, publishing):
    router.include_router(_m.router)
