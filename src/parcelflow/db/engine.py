"""SQLAlchemy engine factory.

One function returns an engine for whatever ``DATABASE_URL`` is configured.
Locally that is SQLite (no server needed); the Docker Compose stack points it
at PostgreSQL. The pipeline code never cares which, because it only speaks
SQLAlchemy Core.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event

from ..config import get_settings


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    # ``future`` engines use SQLAlchemy 2.0 semantics everywhere.
    engine = create_engine(url, future=True)

    # SQLite needs foreign-key enforcement turned on per-connection.
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine
