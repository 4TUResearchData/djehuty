"""Main v2 API router. Aggregates the public and account sub-routers."""

from fastapi import APIRouter

from djehuty.api.v2.account import router as account_router
from djehuty.api.v2.articles import router as articles_router
from djehuty.api.v2.categories import router as categories_router
from djehuty.api.v2.collections import router as collections_router
from djehuty.api.v2.licenses import router as licenses_router

router = APIRouter(prefix="/v2")
router.include_router(articles_router)
router.include_router(collections_router)
router.include_router(categories_router)
router.include_router(licenses_router)
router.include_router(account_router)
