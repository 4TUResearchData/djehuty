"""Umbrella FastAPI app for the new HTTP stack.

Each group PR mounts its router here and registers its RouteGroup. Mounting is
not going live: the dispatcher in djehuty.web.ui picks new vs legacy per request.
"""

import importlib.metadata

from fastapi import FastAPI


def create_app(db) -> FastAPI:
    app = FastAPI(
        title="Djehuty",
        summary="Research data repository for 4TU.ResearchData",
        version=importlib.metadata.version("djehuty"),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.db = db
    return app
