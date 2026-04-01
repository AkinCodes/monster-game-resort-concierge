from __future__ import annotations

import threading
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional
from datetime import datetime, timezone

from ..config import Settings
from ..cctv.logging_utils import logger, DatabaseError

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
    """CREATE TABLE IF NOT EXISTS messages (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role       TEXT NOT NULL,
        content    TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id)
    )""",
    # --- Business Logic: Bookings ---
    """CREATE TABLE IF NOT EXISTS bookings (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_reference TEXT UNIQUE NOT NULL, -- Public UUID-based ID for guests
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
    )""",
    # --- Performance Optimization ---
    """CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)""",
    """CREATE INDEX IF NOT EXISTS idx_bookings_session_id ON bookings(session_id)""",
    """CREATE INDEX IF NOT EXISTS idx_bookings_reference  ON bookings(booking_reference)""",
]


class DatabaseManager:
    def __init__(self, settings: Settings):
        self.db_path = Path(getattr(settings, "sqlite_db", "monster_resort.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"Database transaction failed: {e}")
        finally:
            conn.close()

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        with self.get_connection() as conn:
            yield conn

    def _init_db(self):
        try:
            with self.get_connection() as conn:
                for stmt in DDL:
                    conn.execute(stmt)

                cur = conn.execute("SELECT MAX(version) AS v FROM schema_migrations")
                row = cur.fetchone()
                current = int(row["v"] or 0)

                if current < SCHEMA_VERSION:
                    logger.info("Upgrading schema from %s to %s", current, SCHEMA_VERSION)
                    conn.execute(
                        "INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                        (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
                    )
            logger.info("Database initialized at %s", self.db_path)
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
