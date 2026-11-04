"""Versioned SQLite migrations for the local library.

`database/schema.sql` is the frozen v1 definition: migration 1 reads it
verbatim, so the framework and the file can never drift apart. A database
created before this framework existed (v1 tables present, no
`schema_migrations` table) is recognized as v1 and stamped, never rebuilt,
so its rows survive the upgrade untouched. Later migrations are ordered
SQL applied on top. There is no downgrade support: a database stamped
with a version this code does not know (i.e. newer than the code) raises
`MigrationError` instead of being opened on a guess.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DDL = ROOT / "database" / "schema.sql"

MIGRATIONS_TABLE = "schema_migrations"


class MigrationError(RuntimeError):
    pass


def _v1_sql() -> str:
    return DDL.read_text(encoding="utf-8")


# Ordered (version, name, sql). `sql` is a string, or a zero-arg callable
# returning one (migration 1 defers to database/schema.sql on disk).
MIGRATIONS: list[tuple[int, str, object]] = [
    (1, "initial_schema", _v1_sql),
    (
        2,
        "asset_source_license",
        "ALTER TABLE assets ADD COLUMN source TEXT;\n"
        "ALTER TABLE assets ADD COLUMN license TEXT;",
    ),
    (
        3,
        "jobs_queue",
        "CREATE TABLE IF NOT EXISTS jobs (\n"
        "  job_id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "  kind TEXT NOT NULL,\n"
        "  payload_json TEXT NOT NULL,\n"
        "  state TEXT NOT NULL DEFAULT 'queued'\n"
        "    CHECK(state IN ('queued','running','done','failed')),\n"
        "  worker_id TEXT,\n"
        "  attempts INTEGER NOT NULL DEFAULT 0,\n"
        "  result_json TEXT,\n"
        "  error TEXT,\n"
        "  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n"
        "  claimed_at TEXT,\n"
        "  finished_at TEXT\n"
        ");\n"
        "CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state, job_id);",
    ),
]

LATEST_VERSION = MIGRATIONS[-1][0]
_KNOWN = {version: name for version, name, _ in MIGRATIONS}


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def applied_versions(db: sqlite3.Connection) -> list[int]:
    if not _table_exists(db, MIGRATIONS_TABLE):
        return []
    return [r[0] for r in db.execute(
        f"SELECT version FROM {MIGRATIONS_TABLE} ORDER BY version")]


def current_version(db: sqlite3.Connection) -> int:
    applied = applied_versions(db)
    return max(applied) if applied else 0


def _stamp(db: sqlite3.Connection, version: int) -> None:
    db.execute(
        f"INSERT INTO {MIGRATIONS_TABLE}(version, name) VALUES(?,?)",
        (version, _KNOWN[version]),
    )


def migrate(db: sqlite3.Connection) -> int:
    """Bring `db` to LATEST_VERSION; returns the resulting version.

    Idempotent: a database already at the latest version is untouched.
    Raises MigrationError for a database stamped newer than this code.
    """
    db.execute(
        f"CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} ("
        "version INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    applied = set(applied_versions(db))
    unknown = sorted(applied - set(_KNOWN))
    if unknown:
        raise MigrationError(
            f"database schema version(s) {unknown} are not known to this "
            f"code (latest supported: {LATEST_VERSION}); refusing to open "
            "a newer database with older code"
        )
    # Legacy recognition: a pre-framework database already holds the v1
    # tables. Stamp v1 as applied instead of re-running its DDL over live
    # data; pending later migrations then apply normally.
    if 1 not in applied and _table_exists(db, "assets"):
        _stamp(db, 1)
        applied.add(1)
    for version, _name, sql in MIGRATIONS:
        if version in applied:
            continue
        db.executescript(sql() if callable(sql) else sql)
        _stamp(db, version)
        applied.add(version)
    db.commit()
    return max(applied) if applied else 0
