# from garage import hammer

from __future__ import annotations

import atexit
import time
import threading
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
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
                    print(
                        f"DEBUG [DB]: Upgrading schema from {current} to {SCHEMA_VERSION}"
                    )
                    conn.execute(
                        "INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                        (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
                    )
            print(f"DEBUG [DB]: Database initialized at {self.db_path}")
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

        print(f"DEBUG [DB]: Attempting to create booking record. Ref: {booking_ref}")

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

            print(f"DEBUG [DB]: Success! Booking {booking_ref} saved to SQL.")
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


# One sentence to remember
# CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id) = “Make
# a fast lookup for the session_id column in messages, but don’t make it twice.”


# @contextmanager
# 10 Very Simple Analogies
# 1. Borrowing a library book 📚
# @contextmanager = the librarian system
# get_connection() = borrowing the book
# You get the book (yield)
# When you’re done, you must return it
# The system makes sure the book always gets returned
# 2. Using a bathroom 🚻
# Enter bathroom → door locks
# Do your thing (yield)
# Exit → door unlocks automatically
# You don’t have to remember to unlock it — it just happens.
# 3. Renting a car 🚗
# Pick up the car (open DB connection)
# Drive it (yield)
# Return it clean and fueled (close connection)
# Even if something goes wrong on the drive, the return still happens.
# 4. Borrowing a phone charger 🔌
# Friend hands you the charger
# You charge your phone
# When you’re done, charger goes back to them
# @contextmanager is your friend making sure you don’t walk away with it.


# Polished hotel analogy (exact match)
# Think of @contextmanager like the hotel’s automatic room system, not the maid watching you.
# What actually happens
# You check into the hotel
# → database connection opens
# You turn on the tap
# → you use the connection (yield conn)
# You leave the room
# → no matter what (even if you flood the bathroom)
# The hotel system automatically:
# turns off the tap 🚰
# cleans the room 🧹
# locks the door 🔒
# That automatic cleanup only exists because the hotel is wired for it.
# That wiring = @contextmanager


# so what happens if this is missing -
# conn.row_factory = sqlite3.Row

# That line controls how rows come back from SQLite.
# If it’s missing, nothing explodes—but the shape of your query
# results changes in ways that can quietly mess you up.
# Here’s the breakdown 👇

# With this line
# conn.row_factory = sqlite3.Row

# Each row behaves like a dictionary + tuple hybrid.
# You can do:
# row["username"]
# row["email"]
# row[0]

# This is great because:


# Code is more readable


# Column order doesn’t matter


# Safer when schemas change


# Example:
# cur.execute("SELECT id, name FROM users")
# row = cur.fetchone()
# print(row["name"])

# ✅ Works

# Without it (default behavior)
# Rows come back as plain tuples:
# (1, "Alice")

# So this:
# row["name"]

# ❌ Breaks with
# TypeError: tuple indices must be integers or slices

# You’re forced to do:
# row[1]  # hope name is always column #1 😬


### What `yield` means (plain English)
# `yield` **hands something out temporarily and then pauses**, expecting to **come back later**.
# `return` **hands something out and ends the function forever**.

# In a `@contextmanager`, that pause-and-resume behavior is *the whole point*.

# ---

# ## 5 very simple analogies

# ### 1️⃣ Lending someone your keys

# * **`yield`**: “Here are my keys—bring them back when you’re done.”
# * **`return`**: “Here are my keys. I’m gone forever.”

# The context manager needs the keys back to lock the door (`close()` the connection).

# ---

# ### 2️⃣ Restaurant table

# * **`yield`**: You sit at the table, eat, then leave so the staff can clean it.
# * **`return`**: You sit at the table and disappear—no cleanup ever happens.

# ---

# ### 3️⃣ Borrowing a library book

# * **`yield`**: You borrow the book, read it, then return it.
# * **`return`**: You borrow the book and the library burns down.

# ---

# ### 4️⃣ Pausing a movie

# * **`yield`**: Pause → do something → resume → finish the movie.
# * **`return`**: Stop the movie and eject the DVD.

# ---

# ### 5️⃣ Bathroom key at a gas station

# * **`yield`**: Take the key, use the bathroom, give it back.
# * **`return`**: Take the key and drive away.

# ---

# ## Why `yield` is required here

# Your code:

# ```python
# @contextmanager
# def session(self) -> Iterator[sqlite3.Connection]:
#     with self.get_connection() as conn:
#         yield conn
# ```

# What actually happens when someone writes:

# ```python
# with db.session() as conn:
#     do_stuff(conn)
# ```

# ### Step-by-step

# 1. `get_connection()` opens the DB
# 2. `yield conn` → **hands the connection to the `with` block**
# 3. `do_stuff(conn)` runs
# 4. The `with` block ends
# 5. Execution **resumes after `yield`**
# 6. `get_connection()` cleans up (connection closes)

# That pause between steps 2 and 5 is **impossible with `return`**.

# ---

# ## Why `return` does NOT work

# If you did this:

# ```python
# @contextmanager
# def session(self):
#     conn = self.get_connection()
#     return conn
# ```

# Then:

# * The function ends immediately
# * Python has **no place to resume**
# * Cleanup code never runs
# * Connections leak 😬

# The context manager protocol literally depends on `yield`.

# ---

# ## One-sentence mental model

# > **`yield` says: “Here, use this—but I’m coming back when you’re done.”**
