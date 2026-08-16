"""SQLite twin migration runner (plan/01 §5.1).

Applies pending versioned .sql scripts from sqlite/migrations/ in filename
order, each inside one transaction, and records them in a schema_migrations
table. Used by the Tauri desktop at startup; here it is a plain Python script
so the twin can be verified headless.

Usage:
    python sqlite/runner.py [db_path]   (default: sqlite/pharmatag.db)
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def run(db_path: str) -> list[str]:
    db_path = str(db_path)
    if db_path != ":memory:" and not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {
            row[0]
            for row in conn.execute("SELECT version FROM schema_migrations")
        }

        applied_now: list[str] = []
        for script in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = script.stem  # e.g. 001_core_schema
            if version in applied:
                continue
            sql = script.read_text(encoding="utf-8")
            try:
                conn.execute("BEGIN")
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(timezone.utc).isoformat()),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            applied_now.append(version)

        conn.commit()
        return applied_now
    finally:
        conn.close()


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parent / "pharmatag.db"
    )
    applied = run(db_path)
    if applied:
        print("applied:", ", ".join(applied))
    else:
        print("already up to date")
    print(f"db: {db_path}")


if __name__ == "__main__":
    main()