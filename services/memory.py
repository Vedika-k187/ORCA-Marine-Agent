"""
ORCA Persistent Session Memory Service
Provides lightweight SQLite-backed persistence for multi-turn conversational context,
detected locations, recent intents, and temporal scopes.
Includes automatic graceful fallback to in-memory storage if SQLite is unavailable.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from services.config import settings

logger = logging.getLogger(__name__)

# Fallback store in case SQLite encounters disk/permission errors
_IN_MEMORY_FALLBACK: Dict[str, Dict[str, Any]] = {}
_SQLITE_ENABLED: bool = True


def get_db_path() -> Path:
    """Returns absolute path to the local SQLite database file."""
    path = settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db(db_path: Optional[Path] = None) -> bool:
    """Initializes SQLite schema for sessions and conversation history."""
    global _SQLITE_ENABLED
    path = db_path or get_db_path()
    try:
        with sqlite3.connect(path, timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orca_sessions (
                    session_id TEXT PRIMARY KEY,
                    context_locations TEXT,
                    context_intent TEXT,
                    context_time_horizon TEXT,
                    last_query TEXT,
                    last_response TEXT,
                    metadata_json TEXT,
                    updated_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    intent TEXT,
                    timestamp TEXT,
                    FOREIGN KEY(session_id) REFERENCES orca_sessions(session_id)
                )
            """)
            conn.commit()
            _SQLITE_ENABLED = True
            return True
    except Exception as e:
        logger.warning(f"Failed to initialize SQLite database ({path}): {e}. Falling back to in-memory.")
        _SQLITE_ENABLED = False
        return False


def save_session(session_id: str, state: Dict[str, Any], db_path: Optional[Path] = None) -> bool:
    """
    Persists session state (locations, intent, time horizon, last turn) into SQLite.
    Falls back gracefully to in-memory store if SQLite is unavailable.
    """
    raw_locs = state.get("target_locations", [])
    loc_names = [
        l.get("name") if isinstance(l, dict) else str(l)
        for l in raw_locs
    ] or state.get("context_locations", [])

    intent = state.get("intent") or state.get("context_intent")
    time_horizon = state.get("time_horizon") or state.get("context_time_horizon")
    last_query = state.get("query", "")
    last_response = state.get("final_response", "")
    now_iso = datetime.now(timezone.utc).isoformat()

    session_record = {
        "session_id": session_id,
        "context_locations": loc_names,
        "context_intent": intent,
        "context_time_horizon": time_horizon,
        "last_query": last_query,
        "last_response": last_response,
        "updated_at": now_iso,
    }

    # Always update in-memory cache as well
    _IN_MEMORY_FALLBACK[session_id] = session_record

    global _SQLITE_ENABLED
    if not _SQLITE_ENABLED:
        return True

    path = db_path or get_db_path()
    try:
        init_db(path)
        with sqlite3.connect(path, timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO orca_sessions (
                    session_id, context_locations, context_intent, context_time_horizon,
                    last_query, last_response, metadata_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                json.dumps(loc_names),
                intent,
                time_horizon,
                last_query,
                last_response[:5000],  # Keep reasonable size
                json.dumps({"persisted_at": now_iso}),
                now_iso,
            ))
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"save_session sqlite error: {e}. Session saved to memory fallback.")
        return True


def load_session(session_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves stored session state for session_id.
    Returns None if session does not exist.
    """
    global _SQLITE_ENABLED
    path = db_path or get_db_path()

    if _SQLITE_ENABLED:
        try:
            init_db(path)
            with sqlite3.connect(path, timeout=5.0) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_id, context_locations, context_intent, context_time_horizon,
                           last_query, last_response, updated_at
                    FROM orca_sessions WHERE session_id = ?
                """, (session_id,))
                row = cursor.fetchone()
                if row:
                    locs = json.loads(row[1]) if row[1] else []
                    return {
                        "session_id": row[0],
                        "context_locations": locs,
                        "context_intent": row[2],
                        "context_time_horizon": row[3],
                        "last_query": row[4],
                        "last_response": row[5],
                        "updated_at": row[6],
                    }
        except Exception as e:
            logger.warning(f"load_session sqlite error: {e}. Falling back to memory.")

    return _IN_MEMORY_FALLBACK.get(session_id)


def append_message(
    session_id: str,
    role: str,
    content: str,
    intent: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> bool:
    """Appends an interaction turn to the persistent log."""
    now_iso = datetime.now(timezone.utc).isoformat()

    global _SQLITE_ENABLED
    if _SQLITE_ENABLED:
        path = db_path or get_db_path()
        try:
            init_db(path)
            with sqlite3.connect(path, timeout=5.0) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO conversation_turns (session_id, role, content, intent, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, role, content[:4000], intent or "", now_iso))
                conn.commit()
                return True
        except Exception as e:
            logger.warning(f"append_message sqlite error: {e}")

    # Fallback log in memory
    sess = _IN_MEMORY_FALLBACK.setdefault(session_id, {"session_id": session_id, "turns": []})
    sess.setdefault("turns", []).append({
        "role": role,
        "content": content,
        "intent": intent,
        "timestamp": now_iso,
    })
    return True


def clear_session(session_id: str, db_path: Optional[Path] = None) -> bool:
    """Clears all session and conversation history records for session_id."""
    if session_id in _IN_MEMORY_FALLBACK:
        del _IN_MEMORY_FALLBACK[session_id]

    global _SQLITE_ENABLED
    if not _SQLITE_ENABLED:
        return True

    path = db_path or get_db_path()
    try:
        init_db(path)
        with sqlite3.connect(path, timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversation_turns WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM orca_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"clear_session sqlite error: {e}")
        return False


def get_session_context(session_id: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Returns safe dictionary with locations and intent for LangGraph planner invocation."""
    sess = load_session(session_id, db_path=db_path)
    if not sess:
        return {
            "context_locations": [],
            "context_intent": None,
            "context_time_horizon": "today",
        }
    return {
        "context_locations": sess.get("context_locations", []),
        "context_intent": sess.get("context_intent"),
        "context_time_horizon": sess.get("context_time_horizon", "today"),
    }
