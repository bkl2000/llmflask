# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import pytest


def test_create_and_get_session(db):
    from llmflask.database import create_session, get_session

    sid = create_session(db, user="testuser", title="Test Chat", model="llama3.1:8b")
    assert sid > 0

    s = get_session(db, sid)
    assert s["title"] == "Test Chat"
    assert s["model"] == "llama3.1:8b"
    assert s["user"] == "testuser"


def test_create_session_ensures_user(db):
    from llmflask.database import create_session, list_users

    create_session(db, user="alice", title="Alice Chat")

    users = list_users(db)
    assert {"name": "alice", "chats": 1} in users


def test_rename_user_updates_sessions(db):
    from llmflask.database import create_session, get_sessions, list_users, rename_user

    create_session(db, user="alice", title="Alice Chat")

    assert rename_user(db, "alice", "carla") == "carla"
    assert get_sessions(db, "alice") == []
    assert get_sessions(db, "carla")[0]["title"] == "Alice Chat"
    assert {"name": "carla", "chats": 1} in list_users(db)


def test_rename_user_rejects_default_and_conflicts(db):
    import pytest
    from llmflask.database import create_session, rename_user

    create_session(db, user="alice", title="A")
    create_session(db, user="bob", title="B")

    with pytest.raises(ValueError):
        rename_user(db, "default", "other")
    with pytest.raises(FileExistsError):
        rename_user(db, "alice", "bob")


def test_delete_user_removes_sessions(db):
    from llmflask.database import create_session, delete_user, get_sessions, list_users

    create_session(db, user="alice", title="A1")
    create_session(db, user="alice", title="A2")

    assert delete_user(db, "alice") == 2
    assert get_sessions(db, "alice") == []
    assert "alice" not in {u["name"] for u in list_users(db)}


def test_delete_user_rejects_default(db):
    import pytest
    from llmflask.database import delete_user

    with pytest.raises(ValueError):
        delete_user(db, "default")


def test_get_sessions_filtered_by_user(db):
    from llmflask.database import create_session, get_sessions

    create_session(db, user="alice", title="Alice Chat")
    create_session(db, user="bob", title="Bob Chat")

    alice_sessions = get_sessions(db, "alice")
    bob_sessions = get_sessions(db, "bob")

    assert len(alice_sessions) == 1
    assert alice_sessions[0]["title"] == "Alice Chat"
    assert len(bob_sessions) == 1
    assert bob_sessions[0]["title"] == "Bob Chat"


def test_get_sessions_ordered(db):
    from llmflask.database import create_session, get_sessions

    create_session(db, user="d", title="First")
    create_session(db, user="d", title="Second")
    sessions = get_sessions(db, "d")
    assert len(sessions) == 2
    assert sessions[0]["title"] == "Second"


def test_update_session_title(db):
    from llmflask.database import create_session, update_session_title, get_session

    sid = create_session(db, user="d", title="Old Title")
    update_session_title(db, sid, "New Title")
    s = get_session(db, sid)
    assert s["title"] == "New Title"


def test_update_session_title_for_user_checks_owner(db):
    from llmflask.database import create_session, get_session, update_session_title_for_user

    sid = create_session(db, user="alice", title="Old Title")

    assert update_session_title_for_user(db, sid, "bob", "Wrong") is False
    assert get_session(db, sid)["title"] == "Old Title"
    assert update_session_title_for_user(db, sid, "alice", "Right") is True
    assert get_session(db, sid)["title"] == "Right"


def test_delete_user_sessions(db):
    from llmflask.database import create_session, delete_user_sessions, get_sessions

    create_session(db, user="todelete", title="Chat 1")
    create_session(db, user="todelete", title="Chat 2")
    create_session(db, user="keep", title="Keep")

    count = delete_user_sessions(db, "todelete")
    assert count == 2

    kept = get_sessions(db, "keep")
    assert len(kept) == 1


def test_delete_all_sessions(db):
    from llmflask.database import create_session, delete_all_sessions, get_sessions

    create_session(db, user="a", title="A")
    create_session(db, user="b", title="B")

    count = delete_all_sessions(db)
    assert count == 2

    assert len(get_sessions(db, "a")) == 0
    assert len(get_sessions(db, "b")) == 0


def test_add_and_get_messages(db):
    from llmflask.database import create_session, add_message, get_messages

    sid = create_session(db, title="Chat")
    add_message(db, sid, "user", "Hello")
    add_message(db, sid, "assistant", "Hi there")

    msgs = get_messages(db, sid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello"
    assert msgs[1]["role"] == "assistant"


def test_delete_session_cascades_messages(db):
    from llmflask.database import create_session, add_message, delete_session, get_messages

    sid = create_session(db, title="To Delete")
    add_message(db, sid, "user", "msg")
    delete_session(db, sid)
    msgs = get_messages(db, sid)
    assert len(msgs) == 0


def test_delete_session_for_user_checks_owner(db):
    from llmflask.database import create_session, delete_session_for_user, get_session

    sid = create_session(db, user="alice", title="Keep")

    assert delete_session_for_user(db, sid, "bob") is False
    assert get_session(db, sid) is not None
    assert delete_session_for_user(db, sid, "alice") is True
    assert get_session(db, sid) is None


def test_messages_ordered_by_id(db):
    from llmflask.database import create_session, add_message, get_messages

    sid = create_session(db, title="Order")
    add_message(db, sid, "user", "first")
    add_message(db, sid, "assistant", "second")
    add_message(db, sid, "user", "third")

    msgs = get_messages(db, sid)
    assert [m["content"] for m in msgs] == ["first", "second", "third"]


def test_init_db_is_idempotent(db):
    from llmflask.database import init_db
    init_db(db)  # second call should not error


def test_migration_adds_user_column(tmp_path):
    import sqlite3
    from llmflask.database import init_db, create_session, get_sessions

    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            model TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

    init_db(db_path)  # should add user column
    sid = create_session(db_path, user="migrated", title="OK")
    sessions = get_sessions(db_path, "migrated")
    assert len(sessions) == 1
    assert sessions[0]["user"] == "migrated"


def test_migration_creates_users_from_existing_sessions(tmp_path):
    import sqlite3
    from llmflask.database import init_db, list_users

    db_path = str(tmp_path / "old-users.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL DEFAULT 'default',
            title TEXT DEFAULT '',
            model TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.execute(
        "INSERT INTO sessions (user, title, model, created_at, updated_at) VALUES ('alice', 'A', '', '', '')"
    )
    conn.commit()
    conn.close()

    init_db(db_path)

    assert {"name": "alice", "chats": 1} in list_users(db_path)
    assert {"name": "default", "chats": 0} in list_users(db_path)


def test_invalid_user_names_rejected(db):
    import pytest
    from llmflask.database import create_session, get_sessions

    with pytest.raises(ValueError):
        create_session(db, user="../bad")
    with pytest.raises(ValueError):
        get_sessions(db, "../bad")


def test_db_connection_closes_after_success(tmp_path):
    import sqlite3
    from llmflask.database import db_connection

    with db_connection(str(tmp_path / "close-success.db")) as conn:
        conn.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        conn.execute("SELECT 1")


def test_db_connection_closes_after_error(tmp_path):
    import sqlite3
    from llmflask.database import db_connection

    with pytest.raises(RuntimeError, match="boom"):
        with db_connection(str(tmp_path / "close-error.db")) as conn:
            raise RuntimeError("boom")

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        conn.execute("SELECT 1")
