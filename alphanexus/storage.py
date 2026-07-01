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

import os
import sqlite3
from pathlib import Path


def database_path() -> str:
    return os.getenv("DATABASE_PATH", "alphanexus.db")


def _connect() -> sqlite3.Connection:
    path = database_path()
    # Rows behave like dicts, so callers can read columns by name.
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create the runs table if it does not exist yet (safe to call anytime)."""
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


def save_run(
    ticker: str,
    strategy: str,
    start_date: str,
    end_date: str,
    interval: str,
    metrics: dict[str, float | int],
) -> int:
    """Insert one completed backtest summary and return its new row id."""
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
        return int(cursor.lastrowid)


def recent_runs(limit: int = 20) -> list[dict]:
    """Return the most recent runs, newest first."""
    init_db()
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
