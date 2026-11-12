"""SQLite connection management, runtime version check, and session handling."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import (
    DEFAULT_DB_PATH,
    MIN_SQLITE_VERSION,
    SCHEMA_SQL_PATH,
    ensure_directories,
)


def verify_sqlite_version(
    min_version: tuple[int, int, int] = MIN_SQLITE_VERSION,
) -> tuple[int, int, int]:
    """Verify the active SQLite runtime meets the minimum version requirement (>= 3.25.0)."""
    current_version = sqlite3.sqlite_version_info
    if current_version < min_version:
        min_str = ".".join(str(part) for part in min_version)
        cur_str = ".".join(str(part) for part in current_version)
        raise RuntimeError(
            f"SQLite >= {min_str} is required for window functions and partial indexes, "
            f"but runtime SQLite version is {cur_str}."
        )
    return current_version


def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enforce foreign-key constraints on every SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()


def get_engine(db_path: Optional[Path] = None, echo: bool = False) -> Engine:
    """Create a SQLAlchemy Engine bound to the target SQLite file with FK enforcement enabled."""
    verify_sqlite_version()
    ensure_directories()
    target_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{target_path.resolve().as_posix()}"
    engine = create_engine(db_url, echo=echo, future=True)
    event.listen(engine, "connect", _set_sqlite_pragma)
    return engine


def init_db(
    engine: Optional[Engine] = None,
    db_path: Optional[Path] = None,
    schema_path: Path = SCHEMA_SQL_PATH,
) -> Engine:
    """Initialize the database using the canonical DDL in database/schema.sql."""
    active_engine = engine if engine is not None else get_engine(db_path=db_path)
    if not schema_path.exists():
        raise FileNotFoundError(f"Canonical schema file not found at: {schema_path}")

    ddl_script = schema_path.read_text(encoding="utf-8")
    raw_conn = active_engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.executescript(ddl_script)
        cursor.execute("PRAGMA foreign_keys = ON;")
        raw_conn.commit()
    finally:
        raw_conn.close()
    return active_engine


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a configured SQLAlchemy sessionmaker for the given Engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of database operations."""
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()