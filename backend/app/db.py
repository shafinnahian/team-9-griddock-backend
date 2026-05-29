"""Database engine + session factory.

The persistence boundary. ORM/SQLAlchemy lives here and in ``models.py`` and the
ETL scripts; services compute on pandas frames warmed from these tables.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # recover from stale connections (container restarts)
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session and ensuring it is closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
