"""Main v3 API router. Aggregates all v3 sub-routers."""

from fastapi import APIRouter

from djehuty.api.v3 import (
    accounts,
    admin,
    authors,
    codemeta,
    explore,
    files,
    groups,
    profile,
    reviews,
    ro_crates,
    ssi,
    statistics,
    tags,
)
from djehuty.api.v3.collections import router as collections_router
from djehuty.api.v3.datasets import router as datasets_router
from djehuty.api.v3.git import router as git_router

router = APIRouter(prefix="/v3")
router.include_router(datasets_router)
router.include_router(collections_router)
router.include_router(profile.router)
router.include_router(reviews.router)
router.include_router(statistics.router)
router.include_router(explore.router)
router.include_router(admin.router)
router.include_router(ssi.router)
router.include_router(ro_crates.router)
router.include_router(codemeta.router)
router.include_router(authors.router)
router.include_router(groups.router)
router.include_router(accounts.router)
router.include_router(tags.router)
router.include_router(files.router)
router.include_router(git_router)
