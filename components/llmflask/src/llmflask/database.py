# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
import re
from collections.abc import Iterator
from typing import Any


USER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. -]{0,39}$")


def normalize_user(name: str | None) -> str:
    user = (name or "default").strip()
    if not user or not USER_NAME_RE.fullmatch(user):
        raise ValueError("invalid user name")
    return user


def get_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_connection(path: str) -> Iterator[sqlite3.Connection]:
    """Yield a configured connection and always close it."""
    conn = get_db(path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(path: str) -> None:
    with db_connection(path) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            name TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL DEFAULT 'default',
            title TEXT NOT NULL DEFAULT 'New Chat',
            model TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)
        _migrate_add_user_column(conn)
        _migrate_users_from_sessions(conn)
        conn.commit()


def _migrate_add_user_column(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(sessions)")
    cols = [r["name"] for r in cur.fetchall()]
    if "user" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN user TEXT NOT NULL DEFAULT 'default'")


def _migrate_users_from_sessions(conn: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO users (name, created_at, updated_at)
        VALUES ('default', ?, ?)
        """,
        (now, now),
    )
    rows = conn.execute("SELECT DISTINCT user FROM sessions WHERE user IS NOT NULL AND TRIM(user) != ''").fetchall()
    for row in rows:
        try:
            user = normalize_user(row["user"])
        except ValueError:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO users (name, created_at, updated_at) VALUES (?, ?, ?)",
            (user, now, now),
        )


def ensure_user(db_path: str, user: str) -> str:
    user = normalize_user(user)
    now = datetime.now(timezone.utc).isoformat()
    with db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (name, created_at, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (user, now, now),
        )
        conn.commit()
    return user


def list_users(db_path: str) -> list[dict[str, Any]]:
    with db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT users.name, COUNT(sessions.id) AS chats
            FROM users
            LEFT JOIN sessions ON sessions.user = users.name
            GROUP BY users.name
            ORDER BY users.name
            """
        ).fetchall()
    return [{"name": r["name"], "chats": r["chats"]} for r in rows]


def rename_user(db_path: str, old_name: str, new_name: str) -> str:
    old_user = normalize_user(old_name)
    new_user = normalize_user(new_name)
    if old_user == "default":
        raise ValueError("default user cannot be renamed")
    if old_user == new_user:
        return old_user

    now = datetime.now(timezone.utc).isoformat()
    with db_connection(db_path) as conn:
        try:
            existing = conn.execute("SELECT name FROM users WHERE name = ?", (old_user,)).fetchone()
            if not existing:
                raise LookupError("user not found")
            conflict = conn.execute("SELECT name FROM users WHERE name = ?", (new_user,)).fetchone()
            if conflict:
                raise FileExistsError("user already exists")

            conn.execute("UPDATE users SET name = ?, updated_at = ? WHERE name = ?", (new_user, now, old_user))
            conn.execute("UPDATE sessions SET user = ?, updated_at = ? WHERE user = ?", (new_user, now, old_user))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return new_user


def delete_user(db_path: str, user: str) -> int:
    user = normalize_user(user)
    if user == "default":
        raise ValueError("default user cannot be deleted")

    with db_connection(db_path) as conn:
        try:
            existing = conn.execute("SELECT name FROM users WHERE name = ?", (user,)).fetchone()
            if not existing:
                raise LookupError("user not found")
            cur = conn.execute("SELECT COUNT(*) FROM sessions WHERE user = ?", (user,))
            count = cur.fetchone()[0]
            conn.execute("DELETE FROM sessions WHERE user = ?", (user,))
            conn.execute("DELETE FROM users WHERE name = ?", (user,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return count


def get_session_for_user(db_path: str, session_id: int, user: str) -> dict[str, Any] | None:
    user = normalize_user(user)
    with db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND user = ?",
            (session_id, user),
        ).fetchone()
    return dict(row) if row else None


def create_session(db_path: str, user: str = "default", title: str = "New Chat", model: str = "") -> int:
    user = ensure_user(db_path, user)
    now = datetime.now(timezone.utc).isoformat()
    with db_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO sessions (user, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (user, title, model, now, now),
        )
        conn.commit()
        sid = cur.lastrowid
    if sid is None:
        raise RuntimeError("session insert returned no id")
    return sid


def update_session_title(db_path: str, session_id: int, title: str) -> None:
    with db_connection(db_path) as conn:
        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, datetime.now(timezone.utc).isoformat(), session_id),
        )
        conn.commit()


def update_session_title_for_user(db_path: str, session_id: int, user: str, title: str) -> bool:
    user = normalize_user(user)
    with db_connection(db_path) as conn:
        cur = conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ? AND user = ?",
            (title, datetime.now(timezone.utc).isoformat(), session_id, user),
        )
        conn.commit()
        changed = cur.rowcount > 0
    return changed


def get_sessions(db_path: str, user: str) -> list[dict[str, Any]]:
    user = normalize_user(user)
    with db_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, user, title, model, created_at, updated_at FROM sessions WHERE user = ? ORDER BY updated_at DESC",
            (user,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_session(db_path: str, session_id: int) -> dict[str, Any] | None:
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def add_message(db_path: str, session_id: int, role: str, content: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with db_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        conn.commit()
        mid = cur.lastrowid
    if mid is None:
        raise RuntimeError("message insert returned no id")
    return mid


def get_messages(db_path: str, session_id: int) -> list[dict[str, Any]]:
    with db_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, session_id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_session(db_path: str, session_id: int) -> None:
    with db_connection(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()


def delete_session_for_user(db_path: str, session_id: int, user: str) -> bool:
    user = normalize_user(user)
    with db_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM sessions WHERE id = ? AND user = ?", (session_id, user))
        conn.commit()
        changed = cur.rowcount > 0
    return changed


def delete_user_sessions(db_path: str, user: str) -> int:
    user = normalize_user(user)
    with db_connection(db_path) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM sessions WHERE user = ?", (user,))
        count = cur.fetchone()[0]
        conn.execute("DELETE FROM sessions WHERE user = ?", (user,))
        conn.commit()
    return count


def delete_all_sessions(db_path: str) -> int:
    with db_connection(db_path) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM sessions")
        count = cur.fetchone()[0]
        conn.execute("DELETE FROM sessions")
        conn.commit()
    return count
