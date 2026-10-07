"""Boot-time gating and migration for the field-level review feature.

Called once from ``djehuty.dispatch.build_wsgi_app`` (the single chokepoint
reached by both the internal server and uWSGI) after the new stack is built.
Enforces the feature's gates and runs its one migration.
"""

import logging
import os
from pathlib import Path

from djehuty.route_groups import target_for_path
from djehuty.web.config import config

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = str(Path(__file__).resolve().parent / "migrations")
_VERSION_TABLE = "review_alembic_version"


def dataset_review_enabled(default="new", overrides=None):
    """True when the flag is on AND the review group resolves to the new stack."""
    if not config.enable_dataset_review:
        return False
    return target_for_path("/review/overview", default, overrides) == "new"


def setup_dataset_review(fastapi_app, default="new", overrides=None):
    """Fail fast if enabled without a DSN; otherwise migrate the review schema.

    Migration runs only in the serving process (not the Werkzeug reloader parent)
    and under uWSGI, so the DDL is applied exactly once per boot.
    """
    if not dataset_review_enabled(default, overrides):
        return

    if config.sql_database_url is None:
        raise RuntimeError(
            "dataset-review is enabled but no SQL database is configured; "
            "the feature requires a PostgreSQL DSN (the 'sql' config block)."
        )

    sql = getattr(fastapi_app.state, "sql", None)
    if sql is None:
        raise RuntimeError(
            "dataset-review is enabled but the SQL store is unavailable; "
            "refusing to start without the review conversation store."
        )

    inside_reload = os.environ.get("WERKZEUG_RUN_MAIN")
    if not (inside_reload or not config.use_reloader):
        return

    sql.migrate(_MIGRATIONS_DIR, _VERSION_TABLE, retries=10, retry_delay=3.0)
    logger.info("Field-level review schema is up to date.")
