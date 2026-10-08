"""Shared page renderer for HTML views on the new stack.

Reproduces the legacy ``WebServer.__render_template`` /
``__base_template_parameters`` context so ``layout.html`` and everything that
extends it renders identically whether served new or legacy. The Jinja
environment mirrors the legacy one (same template roots, autoescape, and the
``css_string`` filter); the per-request context is read straight off the shared
``config`` singleton plus ``db`` permission checks -- no ``djehuty.web.wsgi``.
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

from djehuty.api.dependencies import get_token
from djehuty.utils.convenience import css_string
from djehuty.web.config import config

# Same two loader roots as the legacy environment (wsgi.py): the internal
# template directory and the filesystem root (for absolute static-page paths).
_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "web" / "resources" / "html_templates"
_env = Environment(loader=FileSystemLoader([str(_TEMPLATE_DIR), "/"]), autoescape=True)
_env.filters["css_string"] = css_string

templates = Jinja2Templates(env=_env)


class ViewError(Exception):
    """Carries a ready-made HTML/JSON error response out of a dependency.

    Lets the reviewer-auth dependencies short-circuit with a legacy-shaped
    error page; a type-specific handler (registered below) unwraps it, winning
    over the API's generic ``Exception`` handler.
    """

    def __init__(self, response: Response):
        self.response = response


def _accepts_content_type(request: Request, content_type: str, strict: bool = True) -> bool:
    """Faithful port of legacy ``accepts_content_type``.

    A missing ``Accept`` header counts as ``*/*`` (so ``not strict``); an empty
    one accepts nothing.
    """
    acceptable = request.headers.get("Accept")
    if acceptable is None:
        return not strict
    if not acceptable:
        return False
    exact_match = content_type in acceptable
    if strict:
        return exact_match
    return "*/*" in acceptable or exact_match


def accepts_html(request: Request, strict: bool = False) -> bool:
    """Port of legacy ``accepts_html``."""
    return _accepts_content_type(request, "text/html", strict=strict)


def build_page_context(request: Request, db) -> dict:
    """Build the ``layout.html`` context for a request, matching legacy.

    A plain function (not just a dependency) so error helpers can build the
    context without the dependency-injection machinery. Reproduces
    ``__render_template`` field-for-field, including the quirk that
    ``is_reviewing``/``session_token`` derive from different token sources than
    the ``may_*`` privilege flags.
    """
    token = request.cookies.get("djehuty_session")
    account = db.account_by_session_token(token) if token else None

    context = {
        "nonce": uuid.uuid4().hex,
        "custom_stylesheets": config.custom_stylesheets,
        "djehuty_version": config.djehuty_version,
        "large_footer": config.large_footer,
        "small_footer": config.small_footer,
        "maintenance_mode": config.maintenance_mode,
        "storage_maintenance": config.storage_maintenance,
        "path": request.url.path,
        "sandbox_message": config.sandbox_message,
        "site_description": config.site_description,
        "site_name": config.site_name,
        "site_shorttag": config.site_shorttag,
        "startup_timestamp": config.startup_timestamp,
        "base_url": config.base_url,
        "identity_provider": config.identity_provider,
        "in_production": config.in_production,
        "is_logged_in": account is not None,
        "may_deposit": db.is_depositor(token, account),
        "menu": config.menu,
        "orcid_client_id": config.orcid_client_id,
        "orcid_endpoint": config.orcid_endpoint,
        "publisher_rors": config.publisher_rors,
        "support_email_address": config.support_email_address,
    }

    if account is None:
        context.update(session_token=None, impersonating_account=None, is_reviewing=None)
        return context

    impersonator_token = request.cookies.get("impersonator_djehuty_session")
    is_reviewing = db.may_review(impersonator_token)
    if not is_reviewing:
        is_reviewing = db.may_review_institution(impersonator_token)
    context.update(
        impersonating_account=account if impersonator_token else None,
        is_reviewing=is_reviewing,
        may_administer=db.may_administer(token, account),
        may_impersonate=db.may_impersonate(token, account),
        may_query=db.may_query(token, account),
        may_review=db.may_review(token, account),
        may_review_institution=db.may_review_institution(token, account),
        may_review_integrity=db.may_review_integrity(token, account),
        may_review_quotas=db.may_review_quotas(token, account),
        session_token=get_token(request),
    )
    return context


def render_page(
    request: Request, db, template_name: str, status_code: int = 200, **context
) -> Response:
    """Render a template with the full page context.

    The base context overrides page-specific keys on collision, matching legacy
    ``template.render({**context, **parameters})``. Rendered pages carry the
    legacy ``Server`` header (raw redirects do not).
    """
    merged = {**context, **build_page_context(request, db)}
    response = templates.TemplateResponse(request, template_name, merged, status_code=status_code)
    response.headers["Server"] = config.site_name
    return response


def html_error(request: Request, db, status_code: int) -> Response:
    """Port of legacy ``error_403``/``error_404``: HTML page or JSON by Accept."""
    if _accepts_content_type(request, "text/html", strict=True):
        template = "404.html" if status_code == 404 else "403.html"
        return render_page(request, db, template, status_code=status_code)
    message = "This resource does not exist." if status_code == 404 else "Not allowed."
    response = JSONResponse({"message": message}, status_code=status_code)
    response.headers["Server"] = config.site_name
    return response


def html_authorization_failed(request: Request, db) -> Response:
    """Port of legacy ``error_authorization_failed`` (403)."""
    if _accepts_content_type(request, "text/html", strict=True):
        return render_page(request, db, "403.html", status_code=403)
    response = JSONResponse(
        {"message": "Invalid or unknown session token", "code": "InvalidSessionToken"},
        status_code=403,
    )
    response.headers["Server"] = config.site_name
    return response


def error_406(allowed_formats: str = "text/html") -> Response:
    """Port of legacy ``error_406``."""
    response = PlainTextResponse(f"Acceptable formats: {allowed_formats}", status_code=406)
    response.headers["Server"] = config.site_name
    return response


def error_500() -> Response:
    """Port of legacy ``error_500`` (empty body)."""
    response = Response(content=b"", media_type="application/json", status_code=500)
    response.headers["Server"] = config.site_name
    return response


def register_views_exception_handlers(app: FastAPI) -> None:
    """Register the ``ViewError`` handler so dependencies can emit HTML errors."""

    @app.exception_handler(ViewError)
    async def _handle_view_error(request: Request, exc: ViewError):  # noqa: ARG001
        return exc.response
