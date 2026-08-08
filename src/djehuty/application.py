"""Umbrella FastAPI app for the new HTTP stack.

Each group PR mounts its router here and registers its RouteGroup. Mounting is
not going live: the dispatcher in djehuty.web.ui picks new vs legacy per request.
"""

import importlib.metadata

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from djehuty.api.exceptions import register_exception_handlers
from djehuty.api.v2.router import router as v2_router

_DESCRIPTION = """\
The djehuty REST API for 4TU.ResearchData.

## Authentication

Protected endpoints need a session token in the `Authorization` header. Both of
these are accepted:

```
Authorization: token YOUR_TOKEN
Authorization: YOUR_TOKEN
```

In these docs, click **Authorize** (the lock) and paste the token; it is then
sent with every request. From the command line:

```
curl -H "Authorization: token YOUR_TOKEN" https://data.4tu.nl/v2/account
```
"""


def create_app(db, email=None) -> FastAPI:
    app = FastAPI(
        title="Djehuty",
        summary="Research data repository for 4TU.ResearchData",
        description=_DESCRIPTION,
        version=importlib.metadata.version("djehuty"),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.db = db
    app.state.email = email

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["Number-Of-Records", "Number-Of-Returned-Records"],
    )
    register_exception_handlers(app)
    app.include_router(v2_router)
    return app
