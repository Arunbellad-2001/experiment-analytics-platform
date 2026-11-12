"""Shared pytest fixtures for isolated SQLite database testing."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from database.connection import init_db, session_scope


@pytest.fixture()
def temp_db_path(tmp_path: Path) -> Path:
    """Return an isolated temporary SQLite database path."""
    return tmp_path / "test_experiment_analytics.db"


@pytest.fixture()
def db_engine(temp_db_path: Path) -> Generator[Engine, None, None]:
    """Initialize a fresh SQLite database from database/schema.sql for each test."""
    engine = init_db(db_path=temp_db_path)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Provide a transactional SQLAlchemy session bound to the initialized test database."""
    with session_scope(db_engine) as session:
        yield session