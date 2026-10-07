"""Neutral relational-store (PostgreSQL / SQLAlchemy / Alembic) foundation.

A domain-neutral SQL layer for the new stack: a configured engine on
``app.state.sql`` plus a per-feature Alembic harness, so any feature (field-level
review, a future usage-statistics redesign, …) can keep relational data in one
shared PostgreSQL instance with its own tables and migration history. Nothing
here imports ``djehuty.web.wsgi``.
"""

from djehuty.services.sql.alembic_support import run_migrations
from djehuty.services.sql.database import SqlDatabase
from djehuty.services.sql.engine import create_sql_engine
from djehuty.services.sql.migrate import upgrade_to_head

__all__ = ["SqlDatabase", "create_sql_engine", "run_migrations", "upgrade_to_head"]
