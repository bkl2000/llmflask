#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
"""Chat-Verwaltung: Löscht Sessions eines Users oder aller User."""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from llmflask.database import delete_user_sessions, delete_all_sessions, init_db, list_users


def main():
    parser = argparse.ArgumentParser(
        description="Lösche Chat-Sessions aus der LLMFlask-Datenbank.",
    )
    parser.add_argument("--db", type=str, default="chat.db", help="SQLite-Datenbank (default: chat.db)")
    parser.add_argument("--delete", action="store_true", help="Chats löschen")
    parser.add_argument("--list", action="store_true", help="Chats auflisten")
    parser.add_argument("--users", action="store_true", help="Alle Benutzernamen auflisten")
    parser.add_argument("--user", type=str, help="Nur diesen User betreffen")
    parser.add_argument("--all", action="store_true", help="Alle User betreffen")
    args = parser.parse_args()

    init_db(args.db)

    if not args.list and not args.delete and not args.users:
        parser.print_help()
        sys.exit(1)

    if args.users:
        rows = list_users(args.db)
        print(f"{'User':<16} Sessions")
        print("-" * 30)
        for r in rows:
            print(f"{r['name']:<16} {r['chats']}")
        print(f"\n{len(rows)} User")
        return

    if args.list and (args.user or args.all):
        from llmflask.database import get_sessions
        conn, rows = None, []
        if args.all:
            conn = sqlite3.connect(args.db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, user, title, updated_at FROM sessions ORDER BY updated_at DESC").fetchall()
            conn.close()
        elif args.user:
            rows = get_sessions(args.db, args.user)
        print(f"{'ID':<5} {'User':<12} {'Title':<40} {'Updated'}")
        print("-" * 80)
        for r in rows:
            d = dict(r)
            print(f"{d['id']:<5} {d.get('user','-')[:11]:<12} {d['title'][:38]:<40} {d['updated_at'][:19]}")
        print(f"\n{len(rows)} Sessions")
        return

    if args.all:
        count = delete_all_sessions(args.db)
        print(f"Alle {count} Sessions gelöscht.")
    elif args.user:
        count = delete_user_sessions(args.db, args.user)
        print(f"{count} Sessions von User '{args.user}' gelöscht.")
    else:
        print("Bitte --user oder --all angeben.")
        sys.exit(1)


if __name__ == "__main__":
    main()
