"""DOI badge SVG endpoints for the v3 API."""

from pathlib import Path

from fastapi import APIRouter, Depends, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape

from djehuty.api.dependencies import get_db
from djehuty.api.exceptions import NotFoundError
from djehuty.utils.convenience import parses_to_int
from djehuty.web import validator
from djehuty.web.config import config

router = APIRouter(tags=["V3 / Datasets / Badges"])


# Jinja env for the badge.svg template rendered by the DOI-badge endpoints.
_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "web" / "resources" / "html_templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "svg"]),
)


def _dataset_by_id_or_uri(db, identifier: str, version: int | None):
    """Resolve a published dataset by numeric id or container UUID.

    Faithful port of the legacy ``__dataset_by_id_or_uri`` helper: returns the
    matching record, or ``None`` when the identifier is unknown or malformed
    (neither an integer nor a UUID). AS-IS (#111): the DOI-badge handler
    dereferences the result without a None guard, so an unknown dataset flows
    into ``None[...]`` -> TypeError -> HTTP 500, exactly as legacy.
    """
    parameters = {
        "is_published": True,
        "is_latest": False,
        "is_under_review": None,
        "version": version,
        "account_uuid": None,
        "use_cache": True,
        "limit": 1,
    }
    try:
        if parses_to_int(identifier):
            return db.datasets(dataset_id=int(identifier), **parameters)[0]
        if validator.is_valid_uuid(identifier):
            return db.datasets(container_uuid=identifier, **parameters)[0]
        return None
    except IndexError:
        return None


def _render_doi_badge(db, dataset_id: str, version: int | None) -> Response:
    # AS-IS (#111): faithful port of legacy api_v3_doi_badge. The dataset is
    # resolved with no None guard, so an unknown or malformed identifier
    # crashes on None[...] (TypeError -> HTTP 500); only a missing doi key
    # (KeyError) on an existing record maps to 404, mirroring legacy's bare
    # `except KeyError`.
    try:
        dataset = _dataset_by_id_or_uri(db, dataset_id, version)
        doi = dataset["container_doi"] if version is None else dataset["doi"]
        body = _jinja_env.get_template("badge.svg").render(
            doi=doi,
            version=version,
            color=config.colors["primary-color"],
        )
        return Response(content=body, media_type="image/svg+xml")
    except KeyError as error:
        raise NotFoundError() from error


@router.get(
    "/datasets/{dataset_id}/doi-badge.svg",
    summary="DOI badge SVG (latest version)",
)
def get_doi_badge(dataset_id: str, db=Depends(get_db)):
    return _render_doi_badge(db, dataset_id, version=None)


@router.get(
    "/datasets/{dataset_id}/doi-badge-v{version}.svg",
    summary="DOI badge SVG for a specific version",
)
def get_doi_badge_versioned(dataset_id: str, version: int, db=Depends(get_db)):
    return _render_doi_badge(db, dataset_id, version=version)
