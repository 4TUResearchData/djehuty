"""SQLAlchemy engine factory for the shared relational store.

Importing this module has no side effects: an engine is created only when a
feature is given a configured DSN, so deployments without the SQL store pay
nothing. The driver comes from the DSN (e.g. ``postgresql+psycopg://``).
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_sql_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine for a relational-store DSN."""
    return create_engine(database_url, future=True, pool_pre_ping=True)
