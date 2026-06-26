# modules/db_manager.py
# Mantra V2 — SQLite Database Manager
# ====================================
# Single source of truth for all database interactions in the V2 pipeline.
# Handles: command logs, adaptive corrections, app registry,
#          macro storage, and user preferences.
#
# Security note (research paper point):
#   Every query in this module uses SQLite parameterised form:
#       cursor.execute("SELECT … WHERE col = ?", (value,))
#   This completely prevents SQL injection regardless of user input content,
#   because the driver transmits parameters as typed data — never as raw SQL text.
#
# All other modules import from here. Never write raw SQL elsewhere.

import sqlite3
import os
import json
from typing import Optional

# ── Database file location ────────────────────────────────────────────────────
# Stored in <project_root>/data/mantra_v2.db.
# The data/ directory is created automatically on first run.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
DB_PATH   = os.path.join(_DATA_DIR, "mantra_v2.db")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection.

    Settings applied:
    - **WAL journal mode** — allows concurrent reads while a write is in
      progress; safe for the background voice thread writing while the main
      thread reads.
    - **Foreign keys ON** — enforces referential integrity.
    - **row_factory = sqlite3.Row** — rows behave like dicts (``row["col"]``).

    Returns:
        An open ``sqlite3.Connection`` (caller must close it).
    """
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn


def _execute(sql: str, params: tuple = (), fetch: Optional[str] = None):
    """Execute one parameterised SQL statement and return results.

    All SQL in this module flows through this single helper so that:
    - parameterised queries are enforced at the call site,
    - connections are always closed (via ``finally``),
    - errors are wrapped with context for easier debugging.

    Args:
        sql:    The SQL statement. Always use ``?`` placeholders — never
                f-strings or string concatenation.
        params: Tuple of values bound to the ``?`` placeholders.
        fetch:  ``None`` for write operations (INSERT/UPDATE/DELETE/CREATE),
                ``"one"`` to return one ``Row | None``,
                ``"all"`` to return a list of ``Row``.

    Returns:
        - ``fetch=None``  → last inserted row-id (int)
        - ``fetch="one"`` → ``sqlite3.Row | None``
        - ``fetch="all"`` → ``list[sqlite3.Row]``

    Raises:
        RuntimeError: Wraps any ``sqlite3.Error`` with the SQL and params.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(sql, params)  # parameterised — injection-safe
        conn.commit()
        if fetch == "one":
            return cursor.fetchone()
        if fetch == "all":
            return cursor.fetchall()
        return cursor.lastrowid
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(
            f"[db_manager] SQL error: {e}\nSQL: {sql}\nParams: {params}"
        )
    finally:
        conn.close()


# ── Schema initialisation ──────────────────────────────────────────────────────

def init_db() -> None:
    """Create all V2 tables if they do not already exist.

    Safe to call on every application start — uses ``CREATE TABLE IF NOT EXISTS``
    so existing data is never overwritten.

    Tables created
    ──────────────
    command_log      — full audit trail of every command execution
    corrections      — adaptive learning: user-supplied intent corrections
    app_database     — installed-app registry populated by the scanner
    macros           — recorded keyboard/mouse workflows (Phase 5)
    user_preferences — key-value settings store
    """
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = _get_connection()
    try:
        cur = conn.cursor()

        # ── 1. command_log ────────────────────────────────────────────────────
        # Full audit trail of every command the user issues.
        # Used by: GUI History tab, research paper latency metrics,
        #          context_memory.py long-term persistence.
        #
        # Column notes:
        #   action      — verb describing what was done ("opened", "deleted", …)
        #   entity_type — one of: app | file | folder | command | text
        #   entity_value— the concrete target ("Notepad", "report.pdf", …)
        #   intent      — the intent string produced by intent_module
        #   success     — 1 = succeeded, 0 = failed (INTEGER for easy AVG queries)
        #   latency_ms  — wall-clock execution time in milliseconds
        cur.execute("""
            CREATE TABLE IF NOT EXISTS command_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                action       TEXT    NOT NULL,
                entity_type  TEXT,
                entity_value TEXT,
                intent       TEXT,
                success      INTEGER DEFAULT 1,
                latency_ms   INTEGER,
                timestamp    TEXT    DEFAULT (datetime('now'))
            )
        """)

        # ── 2. corrections ────────────────────────────────────────────────────
        # User-supplied intent corrections for adaptive learning.
        # Parameterised queries guard against injection even when utterance
        # contains quotes or special characters.
        #
        # Column notes:
        #   frequency  — incremented each time the same correction is confirmed;
        #                adaptive_learning.py only fires when frequency >= 2
        #   last_seen  — updated every time the correction is confirmed
        cur.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                utterance      TEXT    NOT NULL,
                wrong_intent   TEXT,
                correct_intent TEXT    NOT NULL,
                frequency      INTEGER DEFAULT 1,
                last_seen      TEXT    DEFAULT (datetime('now'))
            )
        """)

        # ── 3. app_database ───────────────────────────────────────────────────
        # Populated at startup by the Windows registry / filesystem scanner
        # in app_controller.py.  Used for fuzzy app-name matching.
        #
        # Column notes:
        #   source — 'registry_machine' | 'registry_user' | 'scan'
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_database (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name     TEXT    NOT NULL,
                exe_path         TEXT    NOT NULL UNIQUE,
                install_location TEXT,
                source           TEXT,
                last_updated     TEXT    DEFAULT (datetime('now'))
            )
        """)


        # ── 4. macros ─────────────────────────────────────────────────────────
        # Named keyboard/mouse workflows captured by pynput (Phase 5).
        # 'steps' is a JSON array of {type, data, delay_ms} objects.
        #
        # Column notes:
        #   macro_name — UNIQUE so "save" is an upsert
        #   run_count  — incremented each replay for analytics
        cur.execute("""
            CREATE TABLE IF NOT EXISTS macros (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                macro_name TEXT    UNIQUE NOT NULL,
                steps      TEXT    NOT NULL,
                created_at TEXT    DEFAULT (datetime('now')),
                run_count  INTEGER DEFAULT 0
            )
        """)

        # ── 5. user_preferences ───────────────────────────────────────────────
        # Simple key-value store for runtime settings.
        # Example: key='tts_enabled', value='true'
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.commit()
        print("[db_manager] Database ready:", DB_PATH)

    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"[db_manager] Schema init failed: {e}")
    finally:
        conn.close()


# ── Command Log API ───────────────────────────────────────────────────────────

def log_command(
    action: str,
    entity_type: Optional[str] = None,
    entity_value: Optional[str] = None,
    intent: Optional[str] = None,
    success: int = 1,
    latency_ms: Optional[int] = None,
) -> int:
    """Insert one command execution record into ``command_log``.

    All parameters are bound via ``?`` placeholders — safe against injection.

    Args:
        action:       Verb describing the action ("opened", "deleted", …).
        entity_type:  One of ``app``, ``file``, ``folder``, ``command``, ``text``.
        entity_value: Concrete target, e.g. ``"Notepad"``, ``"report.pdf"``.
        intent:       Intent string from intent_module, e.g. ``"open_app"``.
        success:      ``1`` if the command succeeded, ``0`` if it failed.
        latency_ms:   Wall-clock execution time in milliseconds.

    Returns:
        The ``id`` of the newly inserted row.
    """
    return _execute(
        """INSERT INTO command_log
               (action, entity_type, entity_value, intent, success, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (action, entity_type, entity_value, intent, success, latency_ms),
    )


def get_recent_commands(limit: int = 20) -> list:
    """Return the *limit* most recent command log entries as a list of dicts.

    Used by the GUI History tab and context_memory long-term recall.

    Args:
        limit: Maximum number of rows to return (default 20).

    Returns:
        List of dicts with all ``command_log`` columns.
    """
    rows = _execute(
        "SELECT * FROM command_log ORDER BY timestamp DESC LIMIT ?",
        (limit,),
        fetch="all",
    )
    return [dict(row) for row in rows] if rows else []


def get_command_stats() -> dict:
    """Return aggregate statistics from ``command_log`` for the research paper.

    Returns:
        Dict with keys: ``total``, ``success_count``, ``fail_count``,
        ``avg_latency_ms``, ``success_rate_pct``.
    """
    row = _execute(
        """SELECT
               COUNT(*)                          AS total,
               SUM(success)                      AS success_count,
               SUM(1 - success)                  AS fail_count,
               ROUND(AVG(latency_ms), 2)          AS avg_latency_ms
           FROM command_log""",
        fetch="one",
    )
    if not row or not row["total"]:
        return {"total": 0, "success_count": 0, "fail_count": 0,
                "avg_latency_ms": None, "success_rate_pct": None}

    total   = row["total"]
    success = row["success_count"] or 0
    return {
        "total":           total,
        "success_count":   success,
        "fail_count":      row["fail_count"] or 0,
        "avg_latency_ms":  row["avg_latency_ms"],
        "success_rate_pct": round(success / total * 100, 2),
    }


# ── Corrections (Adaptive Learning) API ──────────────────────────────────────

def add_correction(
    utterance: str,
    wrong_intent: Optional[str],
    correct_intent: str,
) -> None:
    """Store a user correction, incrementing frequency on duplicates.

    Uses a SELECT-then-INSERT-or-UPDATE pattern with parameterised queries
    so the logic is explicit and injection-safe.

    Args:
        utterance:      Raw user input that was mis-classified.
        wrong_intent:   The intent the system wrongly assigned (may be None).
        correct_intent: The intent the user confirmed is correct.
    """
    existing = _execute(
        "SELECT id FROM corrections WHERE utterance = ? AND correct_intent = ?",
        (utterance, correct_intent),
        fetch="one",
    )
    if existing:
        _execute(
            """UPDATE corrections
               SET frequency = frequency + 1,
                   last_seen = datetime('now')
               WHERE id = ?""",
            (existing["id"],),
        )
    else:
        _execute(
            """INSERT INTO corrections (utterance, wrong_intent, correct_intent)
               VALUES (?, ?, ?)""",
            (utterance, wrong_intent, correct_intent),
        )


def get_all_corrections() -> list:
    """Return all corrections with ``frequency >= 2`` for adaptive re-ranking.

    Only confirmed corrections (seen at least twice) are returned to prevent
    a single accidental correction from permanently hijacking a command.

    Returns:
        List of dicts with all ``corrections`` columns.
    """
    rows = _execute(
        "SELECT * FROM corrections WHERE frequency >= 2 ORDER BY frequency DESC",
        fetch="all",
    )
    return [dict(row) for row in rows] if rows else []


def delete_correction(correction_id: int) -> bool:
    """Delete a stored correction by primary key.

    Args:
        correction_id: The ``id`` of the correction to remove.

    Returns:
        ``True`` if a row was deleted, ``False`` if the id was not found.
    """
    before = _execute(
        "SELECT id FROM corrections WHERE id = ?", (correction_id,), fetch="one"
    )
    if before:
        _execute("DELETE FROM corrections WHERE id = ?", (correction_id,))
        return True
    return False


# ── App Database API ──────────────────────────────────────────────────────────

def upsert_app(
    display_name: str,
    exe_path: str,
    install_location: Optional[str] = None,
    source: Optional[str] = None,
) -> None:
    """Insert or update one entry in ``app_database``.

    Uses an upsert pattern: if an app with the same ``exe_path`` already
    exists, its display_name, install_location, and source are refreshed.

    Args:
        display_name:     Human-readable name, e.g. ``"Google Chrome"``.
        exe_path:         Full path to the executable.
        install_location: Parent directory of the install (optional).
        source:           One of ``"registry_machine"``, ``"registry_user"``,
                          ``"scan"``.
    """
    _execute(
        """INSERT INTO app_database (display_name, exe_path, install_location, source)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(exe_path) DO UPDATE SET
               display_name     = excluded.display_name,
               install_location = excluded.install_location,
               source           = excluded.source,
               last_updated     = datetime('now')""",
        (display_name, exe_path, install_location, source),
    )


def get_all_apps() -> list:
    """Return all apps in the registry as a list of dicts.

    Used by ``app_controller.py`` for fuzzy app-name matching.

    Returns:
        List of dicts with keys: ``display_name``, ``exe_path``,
        ``install_location``, ``source``, ``last_updated``.
    """
    rows = _execute(
        "SELECT * FROM app_database ORDER BY display_name",
        fetch="all",
    )
    return [dict(row) for row in rows] if rows else []


def clear_app_database() -> None:
    """Wipe all app entries so the scanner can rebuild from scratch."""
    _execute("DELETE FROM app_database")


# ── Macros API ────────────────────────────────────────────────────────────────

def save_macro(macro_name: str, steps: list) -> None:
    """Persist a named macro (upsert by ``macro_name``).

    ``steps`` is serialised to a JSON string before storage.
    Overwrites the existing macro if the name already exists.

    Args:
        macro_name: Unique identifier for the macro.
        steps:      List of step dicts, e.g.
                    ``[{"type": "key_press", "data": "ctrl+c", "delay_ms": 50}]``.
    """
    _execute(
        """INSERT INTO macros (macro_name, steps)
           VALUES (?, ?)
           ON CONFLICT(macro_name) DO UPDATE SET
               steps      = excluded.steps,
               created_at = datetime('now'),
               run_count  = 0""",
        (macro_name, json.dumps(steps)),
    )


def get_macro(macro_name: str) -> Optional[list]:
    """Retrieve the steps for a named macro.

    Increments ``run_count`` on each successful retrieval for analytics.

    Args:
        macro_name: The name of the macro to retrieve.

    Returns:
        List of step dicts, or ``None`` if the macro does not exist.
    """
    row = _execute(
        "SELECT id, steps FROM macros WHERE macro_name = ?",
        (macro_name,),
        fetch="one",
    )
    if not row:
        return None
    _execute(
        "UPDATE macros SET run_count = run_count + 1 WHERE id = ?",
        (row["id"],),
    )
    return json.loads(row["steps"])


def list_macros() -> list:
    """Return metadata for all saved macros (no steps payload).

    Returns:
        List of dicts with keys: ``macro_name``, ``created_at``, ``run_count``.
    """
    rows = _execute(
        "SELECT macro_name, created_at, run_count FROM macros ORDER BY created_at DESC",
        fetch="all",
    )
    return [dict(row) for row in rows] if rows else []


def delete_macro(macro_name: str) -> bool:
    """Delete a macro by name.

    Args:
        macro_name: The macro to delete.

    Returns:
        ``True`` if it existed and was deleted, ``False`` otherwise.
    """
    before = _execute(
        "SELECT id FROM macros WHERE macro_name = ?", (macro_name,), fetch="one"
    )
    if before:
        _execute("DELETE FROM macros WHERE macro_name = ?", (macro_name,))
        return True
    return False


# ── User Preferences API ──────────────────────────────────────────────────────

def set_preference(key: str, value: str) -> None:
    """Upsert a user preference key-value pair.

    Args:
        key:   Preference identifier, e.g. ``"tts_enabled"``.
        value: String value, e.g. ``"true"``.
    """
    _execute(
        """INSERT INTO user_preferences (key, value)
           VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET
               value      = excluded.value,
               updated_at = datetime('now')""",
        (key, str(value)),
    )


def get_preference(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve a user preference by key.

    Args:
        key:     Preference identifier.
        default: Value to return if the key does not exist.

    Returns:
        The stored string value, or *default* if not found.
    """
    row = _execute(
        "SELECT value FROM user_preferences WHERE key = ?",
        (key,),
        fetch="one",
    )
    return row["value"] if row else default


def get_all_preferences() -> dict:
    """Return all preferences as a plain ``{key: value}`` dict."""
    rows = _execute("SELECT key, value FROM user_preferences", fetch="all")
    return {row["key"]: row["value"] for row in rows} if rows else {}


# ── Auto-initialise on import ─────────────────────────────────────────────────
# Any module that does `from modules.db_manager import ...` will automatically
# trigger schema creation if the DB does not exist yet.
init_db()
