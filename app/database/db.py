from __future__ import annotations

import re
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..config import Settings
from ..monitoring.logging_utils import logger, DatabaseError

# Incremented to 3 to reflect the addition of booking_reference
SCHEMA_VERSION = 3

DDL = [
    # --- System & Migration Tracking ---
    """CREATE TABLE IF NOT EXISTS schema_migrations (
        version    INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )""",
    # --- Conversation State & Memory ---
    """CREATE TABLE IF NOT EXISTS sessions (
        session_id    TEXT PRIMARY KEY,
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        summary       TEXT,
        metadata_json TEXT
    )""",
    # --- Performance Optimization ---
    """CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)""",
    """CREATE INDEX IF NOT EXISTS idx_bookings_session_id ON bookings(session_id)""",
    """CREATE INDEX IF NOT EXISTS idx_bookings_reference  ON bookings(booking_reference)""",
]

# Tables with AUTOINCREMENT need different syntax for Postgres (SERIAL/GENERATED)
# We handle this by generating DDL per-backend.

DDL_MESSAGES_SQLITE = """CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
)"""

DDL_MESSAGES_POSTGRES = """CREATE TABLE IF NOT EXISTS messages (
    id         SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
)"""

DDL_BOOKINGS_SQLITE = """CREATE TABLE IF NOT EXISTS bookings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_reference TEXT UNIQUE NOT NULL,
    session_id        TEXT,
    guest_name        TEXT NOT NULL,
    hotel_name        TEXT,
    room_type         TEXT NOT NULL,
    check_in          TEXT NOT NULL,
    check_out         TEXT NOT NULL,
    guests            INTEGER NOT NULL,
    special_requests  TEXT,
    status            TEXT NOT NULL DEFAULT 'confirmed',
    created_at        TEXT NOT NULL
)"""

DDL_BOOKINGS_POSTGRES = """CREATE TABLE IF NOT EXISTS bookings (
    id                SERIAL PRIMARY KEY,
    booking_reference TEXT UNIQUE NOT NULL,
    session_id        TEXT,
    guest_name        TEXT NOT NULL,
    hotel_name        TEXT,
    room_type         TEXT NOT NULL,
    check_in          TEXT NOT NULL,
    check_out         TEXT NOT NULL,
    guests            INTEGER NOT NULL,
    special_requests  TEXT,
    status            TEXT NOT NULL DEFAULT 'confirmed',
    created_at        TEXT NOT NULL
)"""

# Postgres uses ON CONFLICT ... DO UPDATE instead of INSERT OR REPLACE
UPSERT_MIGRATION_SQLITE = (
    "INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES(:version, :applied_at)"
)
UPSERT_MIGRATION_POSTGRES = (
    "INSERT INTO schema_migrations(version, applied_at) VALUES(:version, :applied_at) "
    "ON CONFLICT (version) DO UPDATE SET applied_at = EXCLUDED.applied_at"
)


def _convert_qmarks(sql: str):
    """Convert ?-style positional params to :p0, :p1, ... named params.

    Returns (new_sql, True) if conversion happened, (original_sql, False) otherwise.
    This allows callers that pass (sql, tuple_args) in sqlite3 style to work
    transparently with SQLAlchemy's text() which requires named params.
    """
    if "?" not in sql:
        return sql, False
    parts = sql.split("?")
    new_parts = [parts[0]]
    for i, part in enumerate(parts[1:]):
        new_parts.append(f":p{i}")
        new_parts.append(part)
    return "".join(new_parts), True


class _ConnectionProxy:
    """Wraps a SQLAlchemy connection so that callers using the old sqlite3
    interface (conn.execute(sql, tuple), row['col']) keep working."""

    def __init__(self, sa_conn):
        self._conn = sa_conn

    def execute(self, sql: str, params=None):
        converted_sql, was_converted = _convert_qmarks(sql)
        if params is not None:
            if was_converted and isinstance(params, (tuple, list)):
                # Map positional args to named params :p0, :p1, ...
                params = {f"p{i}": v for i, v in enumerate(params)}
            elif isinstance(params, (tuple, list)) and not was_converted:
                # Named params already in SQL but tuple passed — shouldn't happen
                # but handle gracefully
                pass
        else:
            params = {}

        result = self._conn.execute(text(converted_sql), params)
        return _ResultProxy(result)


class _ResultProxy:
    """Wraps a SQLAlchemy CursorResult to provide sqlite3.Row-like behaviour:
    row['column'] access and .fetchone() / .fetchall() returning dict-like rows.
    """

    def __init__(self, result):
        self._result = result

    def fetchone(self):
        row = self._result.fetchone()
        if row is None:
            return None
        return _RowProxy(row._mapping)

    def fetchall(self):
        rows = self._result.fetchall()
        return [_RowProxy(r._mapping) for r in rows]


class _RowProxy(dict):
    """A dict subclass that also supports attribute access, mimicking sqlite3.Row."""

    def __init__(self, mapping):
        super().__init__(mapping)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql://") or url.startswith("postgres://")


class DatabaseManager:
    def __init__(self, settings: Settings):
        self._db_url = getattr(settings, "database_url", "sqlite:///./monster_resort.db")
        self._is_postgres = _is_postgres(self._db_url)
        self._engine = self._create_engine()
        self._local = threading.local()
        self._init_db()

    def _create_engine(self) -> Engine:
        if self._is_postgres:
            return create_engine(
                self._db_url,
                pool_size=5,
                max_overflow=10,
            )
        else:
            # For SQLite: extract file path for logging purposes
            # sqlite:///./monster_resort.db -> ./monster_resort.db
            db_path_str = self._db_url.replace("sqlite:///", "")
            if db_path_str:
                Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)
            return create_engine(self._db_url)

    @contextmanager
    def get_connection(self) -> Iterator[_ConnectionProxy]:
        conn = self._engine.connect()
        proxy = _ConnectionProxy(conn)
        try:
            yield proxy
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"Database transaction failed: {e}")
        finally:
            conn.close()

    @contextmanager
    def session(self) -> Iterator[_ConnectionProxy]:
        with self.get_connection() as conn:
            yield conn

    def _init_db(self):
        try:
            with self.get_connection() as conn:
                # Create tables — pick correct DDL per backend
                all_ddl = list(DDL)  # copy shared DDL
                if self._is_postgres:
                    # Insert table DDL before the index DDL
                    all_ddl.insert(1, DDL_MESSAGES_POSTGRES)
                    all_ddl.insert(2, DDL_BOOKINGS_POSTGRES)
                else:
                    all_ddl.insert(1, DDL_MESSAGES_SQLITE)
                    all_ddl.insert(2, DDL_BOOKINGS_SQLITE)

                for stmt in all_ddl:
                    conn.execute(stmt)

                cur = conn.execute("SELECT MAX(version) AS v FROM schema_migrations")
                row = cur.fetchone()
                current = int(row["v"] or 0) if row["v"] is not None else 0

                if current < SCHEMA_VERSION:
                    logger.info("Upgrading schema from %s to %s", current, SCHEMA_VERSION)
                    upsert_sql = (
                        UPSERT_MIGRATION_POSTGRES if self._is_postgres
                        else UPSERT_MIGRATION_SQLITE
                    )
                    conn.execute(
                        upsert_sql,
                        {"version": SCHEMA_VERSION, "applied_at": datetime.now(timezone.utc).isoformat()},
                    )
            logger.info("Database initialized (%s)", "PostgreSQL" if self._is_postgres else "SQLite")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")

    def create_booking(
        self,
        session_id: str,
        guest_name: str,
        hotel_name: str,
        room_type: str,
        check_in: str,
        check_out: str,
        guests: int = 1,
        special_requests: str = "",
    ) -> dict:
        # Generate the 8-character reference for the guest
        booking_ref = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        query = """
            INSERT INTO bookings (
                booking_reference, session_id, guest_name, hotel_name,
                room_type, check_in, check_out, guests, special_requests, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self.get_connection() as conn:
                conn.execute(
                    query,
                    (
                        booking_ref,
                        session_id,
                        guest_name,
                        hotel_name,
                        room_type,
                        check_in,
                        check_out,
                        guests,
                        special_requests,
                        now,
                    ),
                )

            logger.info("Booking %s saved to database", booking_ref)
            return {
                "booking_id": booking_ref,
                "guest_name": guest_name,
                "hotel_name": hotel_name,
                "room_type": room_type,
                "check_in": check_in,
                "check_out": check_out,
                "status": "confirmed",
            }
        except Exception as e:
            logger.error(f"Failed to create booking: {e}")
            raise DatabaseError(f"Failed to create booking: {e}")

    def get_booking(self, booking_id: str) -> Optional[dict]:
        # Now searches by the guest-facing booking_reference
        query = "SELECT * FROM bookings WHERE booking_reference = ? OR session_id = ?"
        try:
            with self.get_connection() as conn:
                cur = conn.execute(query, (booking_id, booking_id))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get booking: {e}")
            raise DatabaseError(f"Failed to get booking: {e}")
