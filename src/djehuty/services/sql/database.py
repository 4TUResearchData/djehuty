"""The shared relational-store handle attached to ``app.state.sql``.

Owns a single engine for the configured PostgreSQL (one instance shared by all
features). Features reach it through the ``get_sql`` dependency and use
``engine``/``connect()`` for queries and ``migrate()`` to bring their own schema
to head.
"""

import logging
import time

from djehuty.services.sql.engine import create_sql_engine
from djehuty.services.sql.migrate import upgrade_to_head

logger = logging.getLogger(__name__)


class SqlDatabase:
    """A configured relational store: one engine, shared across features."""

    def __init__(self, database_url):
        self.engine = create_sql_engine(database_url)

    def connect(self):
        """Return a new connection from the engine pool."""
        return self.engine.connect()

    def begin(self):
        """Return a transactional connection context."""
        return self.engine.begin()

    def dispose(self):
        """Dispose the engine's connection pool."""
        self.engine.dispose()

    def migrate(self, script_location, version_table, retries=1, retry_delay=3.0):
        """Bring a feature's schema (at SCRIPT_LOCATION) up to head.

        The DSN is passed with its password intact -- ``str(engine.url)`` would
        mask it to ``***`` and break a password-protected database. RETRIES
        tolerate a still-initialising database (e.g. a cold container).
        """
        url = self.engine.url.render_as_string(hide_password=False)
        attempts = max(1, retries)
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                upgrade_to_head(url, script_location, version_table)
                return
            except Exception as error:  # noqa: BLE001 - surfaced after the retry loop
                last_error = error
                if attempt < attempts:
                    logger.warning(
                        "SQL migration attempt %d/%d failed (%s); retrying in %.1fs.",
                        attempt,
                        attempts,
                        error,
                        retry_delay,
                    )
                    time.sleep(retry_delay)
        raise last_error
