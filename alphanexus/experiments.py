"""Portable experiment snapshots and reproducibility checks (no network I/O)."""

from __future__ import annotations

import hashlib
import json
import math
import platform
from datetime import UTC, datetime
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from alphanexus.validation import validate_prices

SNAPSHOT_VERSION = 1
ENGINE_VERSION = "2"  # SMA-seeded Wilder RSI and audited next-close execution.


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def engine_provenance() -> dict[str, str]:
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for name in ("backtest.py", "strategies.py", "indicators.py", "metrics.py", "validation.py"):
        digest.update(name.encode())
        digest.update((root / name).read_text(encoding="utf-8").encode())
    return {
        "version": ENGINE_VERSION,
        "code_sha256": digest.hexdigest(),
        "python": platform.python_version(),
        "numpy": version("numpy"),
        "pandas": version("pandas"),
    }


def make_snapshot(request: dict, prices: pd.DataFrame, result: dict) -> dict:
    frame = validate_prices(prices)
    timezone = str(frame["date"].dt.tz) if frame["date"].dt.tz is not None else None
    columns = [column for column in ("date", "open", "high", "low", "close", "volume") if column in frame]
    frame = frame[columns].copy()
    frame["date"] = frame["date"].map(lambda value: value.isoformat())
    rows = frame.to_dict(orient="records")
    return {
        "schema_version": SNAPSHOT_VERSION,
        "request": request,
        "engine": engine_provenance().copy(),
        "dataset": {
            "source": prices.attrs.get("source", "unspecified"),
            "captured_at": datetime.now(UTC).isoformat(),
            "downloaded_at": prices.attrs.get("downloaded_at"),
            "sha256": content_hash(rows),
            "row_count": len(rows),
            "actual_start": rows[0]["date"],
            "actual_end": rows[-1]["date"],
            "price_policy": "price_return_no_dividend_cashflows",
            "timezone": timezone,
            "rows": rows,
        },
        "result": result,
    }


def snapshot_prices(snapshot: dict) -> pd.DataFrame:
    if snapshot["schema_version"] != SNAPSHOT_VERSION:
        raise ValueError("unsupported experiment schema version")
    dataset = snapshot["dataset"]
    if content_hash(dataset["rows"]) != dataset["sha256"]:
        raise ValueError("saved input data failed its integrity check")
    frame = pd.DataFrame(dataset["rows"])
    if dataset.get("timezone"):
        # Offset strings can span a daylight-saving transition. Restore the
        # exchange zone through UTC rather than creating mixed-offset objects.
        frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.tz_convert(dataset["timezone"])
    return validate_prices(frame)


def results_match(expected: object, actual: object) -> bool:
    """Compare every metric, equity point and execution with stated tolerances."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        return expected.keys() == actual.keys() and all(
            results_match(value, actual[key]) for key, value in expected.items()
        )
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(results_match(a, b) for a, b in zip(expected, actual, strict=True))
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-8)
    return expected == actual
