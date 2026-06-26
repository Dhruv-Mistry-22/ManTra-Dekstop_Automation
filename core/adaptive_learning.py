"""
adaptive_learning.py – Mantra AI Desktop Automation V2
=======================================================
Stores and retrieves user-supplied intent corrections so the assistant
learns from its own mistakes over time.

Workflow
--------
1. When the user corrects a wrong classification (e.g. via the GUI
   settings panel), call ``store_correction(utterance, wrong, correct)``.
2. Before every intent classification, call
   ``check_correction(raw_utterance)``.  If a high-confidence correction
   is found (rapidfuzz score >= threshold AND seen at least twice),
   return the corrected intent directly – bypassing the ML model.
3. Users can view, audit, and delete stored corrections via
   ``get_all_corrections()`` / ``delete_correction(id)``.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL constants – all queries use ? placeholders (no f-strings in SQL)
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS corrections (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    utterance      TEXT    NOT NULL,
    wrong_intent   TEXT    NOT NULL,
    correct_intent TEXT    NOT NULL,
    frequency      INTEGER NOT NULL DEFAULT 1,
    last_seen      TEXT    NOT NULL
)
"""

_SELECT_EXISTING_SQL = """
SELECT id, frequency
FROM   corrections
WHERE  utterance = ? AND correct_intent = ?
LIMIT  1
"""

_UPDATE_FREQUENCY_SQL = """
UPDATE corrections
SET    frequency = frequency + 1,
       last_seen = ?
WHERE  id = ?
"""

_INSERT_CORRECTION_SQL = """
INSERT INTO corrections (utterance, wrong_intent, correct_intent, last_seen)
VALUES (?, ?, ?, ?)
"""

_SELECT_ALL_SQL = """
SELECT id, utterance, wrong_intent, correct_intent, frequency, last_seen
FROM   corrections
ORDER  BY frequency DESC, last_seen DESC
"""

_DELETE_SQL = """
DELETE FROM corrections
WHERE  id = ?
"""

_SELECT_FOR_MATCH_SQL = """
SELECT utterance, correct_intent, frequency
FROM   corrections
"""


# ---------------------------------------------------------------------------
# CorrectionStore
# ---------------------------------------------------------------------------


class CorrectionStore:
    """Persistent store for user-supplied intent corrections.

    Wraps a SQLite ``corrections`` table and exposes a clean API for
    storing, querying, and deleting corrections.  Fuzzy matching is
    performed with ``rapidfuzz.fuzz.partial_ratio`` so minor re-phrasings
    of the same command are still matched correctly.

    Args:
        db_path: Path to the SQLite database file.  Parent directories are
                 created automatically.  Defaults to ``"data/mantra.db"``.
    """

    def __init__(self, db_path: str | Path = "data/mantra_v2.db") -> None:
        self._db_path: Path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Return a new SQLite connection with Row factory enabled."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create the corrections table if it does not already exist."""
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store_correction(
        self,
        utterance: str,
        wrong_intent: str,
        correct_intent: str,
    ) -> None:
        """Record that *utterance* was mis-classified as *wrong_intent*.

        If the (utterance, correct_intent) pair already exists in the table
        the row's ``frequency`` is incremented by 1 and ``last_seen`` is
        updated to now.  Otherwise a new row is inserted with ``frequency=1``.

        All SQL operations use parameterised queries.

        Args:
            utterance:      The raw text the user typed or spoke.
            wrong_intent:   The intent the system wrongly assigned.
            correct_intent: The intent the user confirmed is correct.
        """
        now = datetime.now().isoformat(timespec="seconds")

        with self._connect() as conn:
            row = conn.execute(
                _SELECT_EXISTING_SQL, (utterance, correct_intent)
            ).fetchone()

            if row:
                # Pair already exists – bump frequency and refresh timestamp
                conn.execute(_UPDATE_FREQUENCY_SQL, (now, row["id"]))
                logger.debug(
                    "[adaptive] Updated correction '%s' -> '%s' (freq=%d)",
                    utterance, correct_intent, row["frequency"] + 1,
                )
            else:
                # New correction – insert fresh row
                conn.execute(
                    _INSERT_CORRECTION_SQL,
                    (utterance, wrong_intent, correct_intent, now),
                )
                logger.info(
                    "[adaptive] Stored new correction '%s': '%s' -> '%s'",
                    utterance, wrong_intent, correct_intent,
                )
            conn.commit()

    def check_correction(
        self,
        utterance: str,
        threshold: int = 85,
    ) -> Optional[str]:
        """Return the learnt correct intent for *utterance*, or ``None``.

        Uses ``rapidfuzz.fuzz.partial_ratio`` to fuzzy-match *utterance*
        against every stored correction.  A correction is applied only when:

        * The fuzzy match score is >= *threshold* (default 85 / 100), **AND**
        * The stored correction has been confirmed at least twice
          (``frequency >= 2``), which prevents a single accidental
          correction from permanently hijacking a command.

        Args:
            utterance:  Raw user input to look up.
            threshold:  Minimum ``partial_ratio`` score (0–100) required for
                        a match to be considered.  Defaults to ``85``.

        Returns:
            The ``correct_intent`` string if a qualifying match is found,
            otherwise ``None``.
        """
        try:
            from rapidfuzz import fuzz as _fuzz
        except ImportError:
            logger.warning(
                "[adaptive] rapidfuzz not installed – skipping correction check. "
                "Run: pip install rapidfuzz"
            )
            return None

        with self._connect() as conn:
            rows = conn.execute(_SELECT_FOR_MATCH_SQL).fetchall()

        if not rows:
            return None

        best_score: float = 0.0
        best_intent: Optional[str] = None

        for row in rows:
            stored_utterance: str = row["utterance"]
            frequency: int        = row["frequency"]
            correct_intent: str   = row["correct_intent"]

            if frequency < 2:
                # Not confirmed enough times yet – skip
                continue

            score: float = _fuzz.partial_ratio(
                utterance.lower().strip(),
                stored_utterance.lower().strip(),
            )

            if score >= threshold and score > best_score:
                best_score  = score
                best_intent = correct_intent

        if best_intent:
            logger.info(
                "[adaptive] Adaptive correction applied: '%s' -> '%s' (score=%.1f)",
                utterance, best_intent, best_score,
            )

        return best_intent

    def get_all_corrections(self) -> list[dict]:
        """Return every stored correction as a list of dicts.

        Results are ordered by frequency descending, then by most recently
        seen.  Intended for the GUI settings panel so users can audit and
        manage what the assistant has learnt.

        Returns:
            List of dicts with keys:
            ``id``, ``utterance``, ``wrong_intent``, ``correct_intent``,
            ``frequency``, ``last_seen``.
            Returns an empty list if no corrections exist.
        """
        with self._connect() as conn:
            rows = conn.execute(_SELECT_ALL_SQL).fetchall()

        return [dict(row) for row in rows]

    def delete_correction(self, correction_id: int) -> bool:
        """Remove the correction identified by *correction_id*.

        Args:
            correction_id: The ``id`` primary key of the row to delete.

        Returns:
            ``True`` if a row was deleted, ``False`` if no row matched the ID.
        """
        with self._connect() as conn:
            cursor = conn.execute(_DELETE_SQL, (correction_id,))
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info("[adaptive] Deleted correction id=%d", correction_id)
        else:
            logger.warning(
                "[adaptive] delete_correction: id=%d not found", correction_id
            )

        return deleted
