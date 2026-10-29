"""Lightweight persistence for completed backtest runs.

We use SQLite (Python's built-in `sqlite3`) so there is no database server to
install: the whole store is a single file on disk. Each function opens its own
short-lived connection, does one job, and closes it. That keeps the code easy
to follow and avoids sharing a connection across FastAPI's worker threads.

Note: on hosts with an ephemeral filesystem (e.g. Render's free tier) this file
is wiped on redeploy. For production you would point DATABASE_PATH at a durable
volume or swap this module for Postgres; the three functions below are the only
seam that would need to change.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from alphanexus.experiments import canonical_json

HISTORY_MAX_RUNS = 1000
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
MAX_HISTORY_BYTES = 128 * 1024 * 1024


def database_path() -> str:
    return os.getenv("DATABASE_PATH", "alphanexus.db")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    # Rows behave like dicts, so callers can read columns by name.
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        # A sqlite3 connection used as a context manager commits on success and
        # rolls back on error, but it does not close. The explicit close below
        # is what actually releases the connection.
        with connection:
            yield connection
    finally:
        connection.close()


_initialised: set[str] = set()


def init_db() -> None:
    """Create the runs table if it does not exist yet (safe to call anytime)."""
    path = database_path()
    if path in _initialised and os.path.exists(path):
        return
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ticker TEXT NOT NULL,
                strategy TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                interval TEXT NOT NULL,
                total_return REAL NOT NULL,
                benchmark_return REAL NOT NULL,
                sharpe_ratio REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                trade_count INTEGER NOT NULL
            )
            """
        )
        # Additive v1 migration: old summary rows remain readable, with no
        # invented inputs. IF NOT EXISTS is safe for simultaneous initializers.
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if schema_version > 1:
            raise sqlite3.OperationalError("database schema is newer than this application")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS experiments (
                run_id INTEGER PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
                snapshot_json TEXT NOT NULL,
                size_bytes INTEGER NOT NULL
            )"""
        )
        connection.execute("PRAGMA user_version = 1")
    _initialised.add(path)


def save_run(
    ticker: str,
    strategy: str,
    start_date: str,
    end_date: str,
    interval: str,
    metrics: dict[str, float | int],
    snapshot: dict | None = None,
) -> int:
    """Insert one completed backtest summary and return its new row id."""
    payload = canonical_json(snapshot) if snapshot is not None else None
    size = len(payload.encode("utf-8")) if payload is not None else 0
    if size > MAX_SNAPSHOT_BYTES:
        raise ValueError("experiment exceeds the 8 MiB save limit")
    init_db()
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO runs (
                ticker, strategy, start_date, end_date, interval,
                total_return, benchmark_return, sharpe_ratio, max_drawdown, trade_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                strategy,
                start_date,
                end_date,
                interval,
                float(metrics["total_return"]),
                float(metrics["benchmark_return"]),
                float(metrics["sharpe_ratio"]),
                float(metrics["max_drawdown"]),
                int(metrics["trade_count"]),
            ),
        )
        run_id = int(cursor.lastrowid)
        if payload is not None:
            connection.execute(
                "INSERT INTO experiments (run_id, snapshot_json, size_bytes) VALUES (?, ?, ?)",
                (run_id, payload, size),
            )
        # Trim in the same transaction as the insert so concurrent writers
        # cannot leave history above the cap after a successful save.
        connection.execute(
            "DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY id DESC LIMIT ?)",
            (HISTORY_MAX_RUNS,),
        )
        # Bound serialized payload storage too. SQLite file allocation may
        # remain larger until vacuumed; this limits retained logical data.
        connection.execute(
            """DELETE FROM runs WHERE id IN (
                SELECT run_id FROM (
                    SELECT run_id, SUM(size_bytes) OVER (ORDER BY run_id DESC) AS retained_bytes
                    FROM experiments
                ) WHERE retained_bytes > ?
            )""",
            (MAX_HISTORY_BYTES,),
        )
        return run_id


def recent_runs(limit: int = 20) -> list[dict]:
    """Return the most recent runs, newest first."""
    # Defence in depth. The API validates this too, but SQLite reads a negative
    # LIMIT as unbounded, so any future caller that skips validation would
    # otherwise pull the whole table. Clamping here makes that impossible.
    limit = max(1, min(int(limit), 100))
    init_db()
    with _connect() as connection:
        rows = connection.execute(
            """SELECT runs.*, EXISTS(SELECT 1 FROM experiments WHERE run_id = runs.id) AS has_snapshot
               FROM runs ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_experiment(run_id: int) -> dict | None:
    init_db()
    with _connect() as connection:
        row = connection.execute(
            """SELECT runs.id, runs.created_at, experiments.snapshot_json
               FROM runs LEFT JOIN experiments ON runs.id = experiments.run_id WHERE runs.id = ?""",
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"], "created_at": row["created_at"],
        "snapshot": json.loads(row["snapshot_json"]) if row["snapshot_json"] is not None else None,
    }
