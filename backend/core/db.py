"""Database engine and session management.

Lazily builds a single SQLAlchemy engine from `settings.database_url` so importing
this module never requires a live DB (Alembic and tests can import models freely).
`get_session` is the FastAPI dependency used by routers later.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill in your "
            "Supabase connection string."
        )
    # pool_pre_ping survives Supabase free-tier connection drops after idle pauses.
    # sqlalchemy_url pins the psycopg (v3) driver.
    return create_engine(settings.sqlalchemy_url, pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, class_=Session)


def get_session() -> Iterator[Session]:
    """Yield a session, closing it afterward. Use as a FastAPI dependency."""
    factory = get_sessionmaker()
    with factory() as session:
        yield session
