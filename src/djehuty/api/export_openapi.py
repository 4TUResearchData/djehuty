"""Write the OpenAPI schemas and a static Swagger UI page to disk.

The runtime docs at /api/docs ask the live app for its schema. The published
documentation has no app behind it, so CI runs this module to dump the same
schemas to files and render a page that reads them. That page pulls Swagger UI
from a CDN, so no asset bundle has to be copied into the site.
"""

import argparse
import json
from pathlib import Path

from djehuty.application import API_VERSIONS, create_app, swagger_html, version_schema


def build_documents(server_url: str | None = None) -> dict[str, dict]:
    """Return {file stem: schema} for the combined and per-version documents.

    Without a server_url no `servers` entry is written, so paths stay relative
    and resolve against whichever instance serves them. djehuty is deployed by
    more than one institution, so this module names none of them.
    """
    # None is the database: nothing is queried while the schema is built.
    app = create_app(None)
    documents = {"swagger": app.openapi()}
    for version in API_VERSIONS:
        documents[f"swagger-{version}"] = version_schema(app, f"/{version}", version)

    if server_url:
        for schema in documents.values():
            schema["servers"] = [{"url": server_url}]
    return documents


def write_documents(out_dir: Path, server_url: str | None = None) -> list[Path]:
    """Write each document as <out_dir>/<stem>.json and return the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for stem, schema in build_documents(server_url).items():
        filepath = out_dir / f"{stem}.json"
        with filepath.open("w", encoding="utf-8") as handle:
            json.dump(schema, handle, indent=2)
        written.append(filepath)
    return written


def write_index(out_dir: Path, server_url: str | None = None) -> Path:
    """Write the Swagger UI page that reads the exported schemas.

    The schema URLs are relative to the page, so the directory can be published
    under any path without rewriting them. "Try it out" is offered only when a
    server_url says where the requests should go.
    """
    urls = [
        {"url": f"swagger-{version}.json", "name": version} for version in reversed(API_VERSIONS)
    ]
    urls.append({"url": "swagger.json", "name": "all"})
    filepath = out_dir / "index.html"
    page = swagger_html(urls, API_VERSIONS[-1], allow_submit=bool(server_url))
    filepath.write_text(page, encoding="utf-8")
    return filepath


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the djehuty OpenAPI schemas.")
    parser.add_argument("out_dir", type=Path, help="directory to write the JSON files into")
    parser.add_argument(
        "--server-url",
        help=(
            "absolute base URL for 'Try it out', e.g. the instance the docs "
            "belong to. Left out of the schema when unset, which also drops "
            "the submit button."
        ),
    )
    args = parser.parse_args()
    paths = write_documents(args.out_dir, args.server_url)
    paths.append(write_index(args.out_dir, args.server_url))
    for path in paths:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
