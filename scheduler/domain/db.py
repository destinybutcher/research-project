"""Database initialization and utilities."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def create_db_engine(db_url: str = "sqlite:///scheduler.db", echo: bool = False):
    """Create SQLAlchemy engine."""
    return create_engine(db_url, echo=echo)


def init_database(db_url: str = "sqlite:///scheduler.db") -> None:
    """Initialize database and create all tables."""
    engine = create_db_engine(db_url)
    Base.metadata.create_all(engine)
    print(f"[INFO] Database initialized: {db_url}")


def get_session_factory(db_url: str = "sqlite:///scheduler.db"):
    """Get a session factory for the database."""
    engine = create_db_engine(db_url)
    return sessionmaker(bind=engine)


def get_session(db_url: str = "sqlite:///scheduler.db") -> Session:
    """Get a new database session."""
    SessionFactory = get_session_factory(db_url)
    return SessionFactory()


def reset_database(db_url: str = "sqlite:///scheduler.db") -> None:
    """Drop all tables and recreate (WARNING: deletes all data!)."""
    engine = create_db_engine(db_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print(f"[WARN] Database reset: {db_url}")

