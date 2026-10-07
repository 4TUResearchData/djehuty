"""Reusable Alembic ``env.py`` logic for the shared relational store.

A feature's ``migrations/env.py`` is three lines: import its ``MetaData``,
import :func:`run_migrations`, and call it. The URL comes from the
``-x db_url=...`` option (set by :mod:`djehuty.services.sql.migrate`) or the
``DJEHUTY_SQL_URL`` environment variable; the version table comes from the
Alembic config, so one database can hold several features' independent
migration histories.
"""

import os

from alembic import context
from sqlalchemy import engine_from_config, pool


def _database_url() -> str:
    """Resolve the relational-store URL from -x db_url or the environment."""
    x_args = context.get_x_argument(as_dictionary=True)
    url = x_args.get("db_url") or os.environ.get("DJEHUTY_SQL_URL")
    if not url:
        raise RuntimeError("No relational-store URL. Pass -x db_url=... or set DJEHUTY_SQL_URL.")
    return url


def run_migrations(target_metadata) -> None:
    """Run the pending migrations for TARGET_METADATA (offline or online)."""
    config = context.config
    version_table = config.get_main_option("version_table")

    if context.is_offline_mode():
        context.configure(
            url=_database_url(),
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            version_table=version_table,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    section = config.get_section(config.config_ini_section, {}) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=version_table,
        )
        with context.begin_transaction():
            context.run_migrations()
