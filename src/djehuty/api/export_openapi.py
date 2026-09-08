"""Write the OpenAPI schema(s) to disk for the static API documentation.

The runtime docs at /api/docs ask the live app for its schema. GitHub Pages has
no app, so CI runs this module to dump the same schema to files that a static
Swagger UI reads.
"""

import argparse
import json
from pathlib import Path

from djehuty.application import API_VERSIONS, create_app, version_schema


def build_documents() -> dict[str, dict]:
    """Return {file stem: schema} for the combined and per-version documents."""
    # None is the database: nothing is queried while the schema is built.
    app = create_app(None)
    documents = {"swagger": app.openapi()}
    for version in API_VERSIONS:
        documents[f"swagger-{version}"] = version_schema(app, f"/{version}", version)
    return documents


def write_documents(out_dir: Path) -> list[Path]:
    """Write each document as <out_dir>/<stem>.json and return the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for stem, schema in build_documents().items():
        filepath = out_dir / f"{stem}.json"
        with filepath.open("w", encoding="utf-8") as handle:
            json.dump(schema, handle, indent=2)
        written.append(filepath)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the djehuty OpenAPI schemas.")
    parser.add_argument("out_dir", type=Path, help="directory to write the JSON files into")
    args = parser.parse_args()
    for path in write_documents(args.out_dir):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
