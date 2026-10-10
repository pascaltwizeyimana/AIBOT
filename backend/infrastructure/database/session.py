"""Database-session factory; callers must explicitly opt into persistence."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_database_engine(database_url: str) -> Engine:
    """Create a pooled database engine without logging its URL or credentials."""
    return create_engine(database_url, pool_pre_ping=True)
