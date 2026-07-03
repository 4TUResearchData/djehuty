"""WSGI dispatcher: send each request to the new FastAPI app or to legacy.

Never imports djehuty.web.wsgi; the legacy app is passed in.
"""

import logging

from djehuty.route_groups import target_for_path

_log = logging.getLogger(__name__)


class WebServiceDispatcher:
    def __init__(self, legacy, new, default="new", overrides=None):
        self.legacy = legacy
        self.new = new
        self.default = default
        self.overrides = overrides or {}

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if target_for_path(path, self.default, self.overrides) == "new":
            return self.new(environ, start_response)
        return self.legacy(environ, start_response)


def build_wsgi_app(legacy_app, db, default="new", overrides=None):
    """Wrap the umbrella app + legacy in the dispatcher; fall back to legacy if
    the new stack cannot be imported."""
    try:
        from a2wsgi import ASGIMiddleware

        from djehuty.application import create_app
    except ImportError as error:
        _log.warning("New HTTP stack unavailable (%s); serving legacy only.", error)
        return legacy_app

    new_app = ASGIMiddleware(create_app(db))
    _log.info(
        "Web service: FastAPI dispatcher active (default=%s, overrides=%s).",
        default,
        overrides or {},
    )
    return WebServiceDispatcher(legacy_app, new_app, default, overrides)
