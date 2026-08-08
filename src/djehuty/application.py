"""Umbrella FastAPI app for the new HTTP stack.

Each group PR mounts its router here and registers its RouteGroup. Mounting is
not going live: the dispatcher in djehuty.web.ui picks new vs legacy per request.
"""

import importlib.metadata
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from djehuty.api.exceptions import register_exception_handlers
from djehuty.api.v2.router import router as v2_router
from djehuty.api.v3.router import router as v3_router

# The API versions served here, oldest first. This single list drives the docs
# selector, the per-version docs pages, and the per-version schemas. Adding a
# version (or retiring one) is a one-line change here plus its router include.
API_VERSIONS = ["v2", "v3"]

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Djehuty API</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"/>
  <link rel="shortcut icon" href="https://data.4tu.nl/static/favicon.ico"/>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
  <script>
    window.ui = SwaggerUIBundle({
      urls: __URLS__,
      "urls.primaryName": "__PRIMARY__",
      dom_id: "#swagger-ui",
      deepLinking: true,
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
      layout: "StandaloneLayout",
    });
  </script>
</body>
</html>"""


def _swagger_html(urls: list, primary: str) -> str:
    """Render the Swagger UI page for the given schema URLs."""
    return _SWAGGER_HTML.replace("__URLS__", json.dumps(urls)).replace("__PRIMARY__", primary)


def _version_schema(app: FastAPI, prefix: str, label: str) -> dict:
    """Return the OpenAPI schema filtered to paths under a version prefix."""
    full = app.openapi()
    schema = dict(full)
    schema["info"] = {**full["info"], "title": f"{full['info']['title']} ({label})"}
    schema["paths"] = {
        path: item for path, item in full["paths"].items() if path.startswith(prefix)
    }
    return schema


def _register_version_docs(app: FastAPI, version: str) -> None:
    """Register a version's filtered schema and its bookmarkable docs page."""

    @app.get(f"/api/openapi/{version}.json", include_in_schema=False)
    def version_schema(version=version) -> JSONResponse:
        return JSONResponse(_version_schema(app, f"/{version}", version))

    @app.get(f"/api/docs/{version}", include_in_schema=False)
    def version_docs(version=version) -> HTMLResponse:
        return HTMLResponse(
            _swagger_html([{"url": f"/api/openapi/{version}.json", "name": version}], version)
        )


_DESCRIPTION = """\
The djehuty REST API for 4TU.ResearchData.

## Authentication

Protected endpoints in both **v2** and **v3** need an API token in the
`Authorization` header. Both of these forms are accepted:

```
Authorization: token YOUR_TOKEN
Authorization: YOUR_TOKEN
```

### Getting a token

Log in, open your [Dashboard](/my/dashboard), and under **Sessions and API
tokens** choose **Create API token**. Your current session token works too, and
stays valid until you log out.

### Using it

In these docs, click **Authorize** (the lock) and paste the token; it is then
sent with every request. From the command line:

```
curl -H "Authorization: token YOUR_TOKEN" https://data.4tu.nl/v2/account
curl -H "Authorization: token YOUR_TOKEN" https://data.4tu.nl/v3/profile
```
"""


def create_app(db, email=None) -> FastAPI:
    app = FastAPI(
        title="Djehuty",
        summary="Research data repository for 4TU.ResearchData",
        description=_DESCRIPTION,
        version=importlib.metadata.version("djehuty"),
        docs_url=None,
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.db = db
    app.state.email = email

    # Combined docs at /api/docs with a version selector (latest first, plus
    # "all"); bookmarkable per-version docs at /api/docs/<version>.
    @app.get("/api/docs", include_in_schema=False)
    def swagger_ui() -> HTMLResponse:
        urls = [{"url": f"/api/openapi/{v}.json", "name": v} for v in reversed(API_VERSIONS)]
        urls.append({"url": "/api/openapi.json", "name": "all"})
        return HTMLResponse(_swagger_html(urls, API_VERSIONS[-1]))

    for _version in API_VERSIONS:
        _register_version_docs(app, _version)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["Number-Of-Records", "Number-Of-Returned-Records"],
    )
    register_exception_handlers(app)
    app.include_router(v2_router)
    app.include_router(v3_router)
    return app
