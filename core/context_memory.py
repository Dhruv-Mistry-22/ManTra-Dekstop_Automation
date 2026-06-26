"""
context_memory.py – Mantra AI Desktop Automation V2
====================================================
Provides the MemoryBank class for tracking recent user actions in both
short-term (in-memory deque) and long-term (SQLite) storage.
"""

from __future__ import annotations

import sqlite3
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ENTITY_TYPES: frozenset[str] = frozenset(
    {"app", "file", "folder", "command", "text"}
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS command_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT    NOT NULL,
    entity_type TEXT    NOT NULL,
    entity_value TEXT   NOT NULL,
    timestamp   TEXT    NOT NULL
)
"""

_INSERT_SQL = """
INSERT INTO command_log (action, entity_type, entity_value, timestamp)
VALUES (?, ?, ?, ?)
"""


# ---------------------------------------------------------------------------
# MemoryBank
# ---------------------------------------------------------------------------


class MemoryBank:
    """Context memory for Mantra AI Desktop Automation V2.

    Maintains a short-term rolling window of the last 10 user actions as a
    ``collections.deque`` and simultaneously persists every action to a
    SQLite database for long-term retrieval.

    Entity types recognised:
        ``app``, ``file``, ``folder``, ``command``, ``text``

    Args:
        db_path: Path (str or Path-like) to the SQLite database file.
                 Parent directories are created automatically.
                 Defaults to ``"data/mantra.db"``.
    """

    def __init__(self, db_path: str | Path = "data/mantra_v2.db") -> None:
        self._lock: threading.Lock = threading.Lock()
        self._memory: deque[dict] = deque(maxlen=10)
        self._db_path: Path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the ``command_log`` table if it does not already exist."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()

    def _persist(self, entry: dict) -> None:
        """Write a single entry dict to the SQLite ``command_log`` table.

        Args:
            entry: A dict with keys ``action``, ``entity_type``,
                   ``entity_value``, and ``timestamp``.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                _INSERT_SQL,
                (
                    entry["action"],
                    entry["entity_type"],
                    entry["entity_value"],
                    entry["timestamp"],
                ),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, action: str, entity_type: str, entity_value: str) -> None:
        """Record a new action in both short-term memory and SQLite.

        Adds an entry ``{action, entity_type, entity_value, timestamp}`` to
        the internal deque (evicting the oldest entry once the window of 10
        is full) and writes the same entry to the SQLite ``command_log``
        table using a parameterised query.

        Args:
            action:       A short description of what was done, e.g.
                          ``"opened"``, ``"closed"``, ``"typed"``.
            entity_type:  One of ``"app"``, ``"file"``, ``"folder"``,
                          ``"command"``, ``"text"``.
            entity_value: The concrete value, e.g. ``"Notepad"``,
                          ``"report.pdf"``.

        Raises:
            ValueError: If ``entity_type`` is not one of the recognised types.
        """
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity_type {entity_type!r}. "
                f"Must be one of {sorted(VALID_ENTITY_TYPES)}."
            )

        entry: dict = {
            "action": action,
            "entity_type": entity_type,
            "entity_value": entity_value,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

        with self._lock:
            self._memory.append(entry)

        # SQLite has its own internal locking; no need to hold _lock here.
        self._persist(entry)

    def get_last(self, entity_type: Optional[str] = None) -> Optional[dict]:
        """Return the most recent memory entry, with optional type filter.

        Iterates the deque from newest to oldest and returns the first entry
        whose ``entity_type`` matches the given filter (if supplied), or the
        very last entry if no filter is given.

        Args:
            entity_type: Optional type to filter on. When ``None`` the most
                         recent entry regardless of type is returned.

        Returns:
            The matching entry dict, or ``None`` if the memory is empty (or
            no entry of the requested type exists).
        """
        with self._lock:
            snapshot = list(self._memory)

        if not snapshot:
            return None

        if entity_type is None:
            return snapshot[-1]

        for entry in reversed(snapshot):
            if entry["entity_type"] == entity_type:
                return entry

        return None

    def resolve_pronoun(self, token: str) -> Optional[str]:
        """Map a natural-language pronoun or reference phrase to an entity value.

        Supported mappings (case-insensitive, leading/trailing whitespace
        stripped):

            ``it``, ``that``           -> Most recent entity (any type)
            ``the file``, ``that file``-> Most recent ``file`` entity
            ``the app``,  ``that app`` -> Most recent ``app`` entity
            ``the folder``, ``that folder`` -> Most recent ``folder`` entity
            ``the command``, ``that command`` -> Most recent ``command`` entity

        Args:
            token: The pronoun or reference phrase from user input.

        Returns:
            The ``entity_value`` string of the resolved entry, or ``None``
            if the token is not recognised or no matching entry exists.
        """
        normalised = token.strip().lower()

        # Generic pronouns -> most recent entity of any type
        if normalised in {"it", "that"}:
            entry = self.get_last()
            return entry["entity_value"] if entry else None

        # Typed references -> most recent entity of a specific type
        type_map: dict[str, str] = {
            "the file":     "file",
            "that file":    "file",
            "the app":      "app",
            "that app":     "app",
            "the folder":   "folder",
            "that folder":  "folder",
            "the command":  "command",
            "that command": "command",
        }

        if normalised in type_map:
            entry = self.get_last(entity_type=type_map[normalised])
            return entry["entity_value"] if entry else None

        return None

    def get_recent(self, n: int = 5) -> list[dict]:
        """Return the *n* most recent memory entries (newest last).

        If the deque holds fewer than *n* entries, all available entries are
        returned.

        Args:
            n: Number of recent entries to retrieve. Must be >= 1.

        Returns:
            A list of entry dicts ordered from oldest to newest, up to *n*
            entries long.

        Raises:
            ValueError: If *n* is less than 1.
        """
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n!r}.")

        with self._lock:
            snapshot = list(self._memory)

        return snapshot[-n:]
