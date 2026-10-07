"""Alembic environment for the field-level review schema.

Three lines of feature glue: the shared harness
(:func:`djehuty.services.sql.run_migrations`) does the offline/online work; the
URL and version table come from the caller (``SqlDatabase.migrate``).
"""

from djehuty.api.services.review.schema import metadata
from djehuty.services.sql import run_migrations

run_migrations(metadata)
