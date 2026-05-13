"""Database bootstrap: optional Postgres create + Alembic migrations."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from rag_document_processor.core.config import Settings

log = structlog.get_logger(__name__)

# Identifier-style Postgres database names (letters, digits, underscore; max 63 chars).
_PG_DB_NAME: re.Pattern[str] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _project_root() -> Path:
    # .../src/rag_document_processor/core/db_bootstrap.py -> repo root
    return Path(__file__).resolve().parents[3]


def _sync_database_url(settings: Settings) -> str:
    if settings.database_url_sync:
        return settings.database_url_sync
    return (settings.database_url or "").replace("+asyncpg", "+psycopg2")


def ensure_postgres_database_exists(settings: Settings) -> None:
    """Connect to `postgres` DB and CREATE DATABASE if the URL database is missing.

    Only runs for PostgreSQL URLs with a simple identifier database name. The DB role
    must be allowed to create databases (often true for local superuser, not on RDS).
    """
    if not settings.database_auto_create:
        return
    sync_url = _sync_database_url(settings)
    if not sync_url or sync_url == "+psycopg2":
        return
    try:
        url = make_url(sync_url)
    except Exception as exc:
        log.warning("database_auto_create_skipped", reason="invalid_url", error=str(exc))
        return
    if url.get_backend_name() != "postgresql":
        log.info("database_auto_create_skipped", reason="not_postgresql", driver=url.drivername)
        return
    dbname = url.database
    if not dbname or dbname in ("postgres", "template0", "template1"):
        return
    if not _PG_DB_NAME.fullmatch(dbname):
        raise ValueError(
            "database_auto_create only supports Postgres database names matching "
            "[A-Za-z_][A-Za-z0-9_]{0,62}. Use a simpler name or create the database manually."
        )
    admin = url.set(database="postgres")
    engine = create_engine(admin, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": dbname},
            ).first()
            if row is not None:
                return
            log.info("creating_postgres_database", database=dbname)
            conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    finally:
        engine.dispose()


@contextmanager
def _database_url_sync_env(url: str):
    key = "DATABASE_URL_SYNC"
    previous = os.environ.get(key)
    os.environ[key] = url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def run_alembic_upgrade_head(settings: Settings) -> None:
    """Run `alembic upgrade head` using the repo's alembic.ini (sync driver URL)."""
    root = _project_root()
    ini_path = root / "alembic.ini"
    if not ini_path.is_file():
        raise FileNotFoundError(f"Missing Alembic config at {ini_path} (unexpected install layout)")

    sync_url = _sync_database_url(settings)
    if not sync_url or sync_url == "+psycopg2":
        raise ValueError("Cannot derive sync database URL for migrations; set DATABASE_URL or DATABASE_URL_SYNC")

    log.info("running_database_migrations", revision="head")
    with _database_url_sync_env(sync_url):
        cfg = Config(str(ini_path))
        command.upgrade(cfg, "head")
    log.info("database_migrations_complete")
