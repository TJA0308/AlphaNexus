"""Domain limits shared by direct engine callers and the HTTP boundary."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# Deliberate research limits, not a claim about realistic brokerage costs.
MAX_COST_BPS = 1_000
MAX_STARTING_CASH = 1_000_000_000_000
MAX_WINDOW = 10_000


def finite_number(name: str, value: float, *, minimum: float, maximum: float, inclusive: bool = True) -> None:
    lower_ok = value >= minimum if inclusive else value > minimum
    if not math.isfinite(value) or not lower_ok or value > maximum:
        relation = "at least" if inclusive else "greater than"
        raise ValueError(f"{name} must be finite, {relation} {minimum} and at most {maximum}")


def validate_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Validate before indicators; never silently drop or repair observations.

    Direct engine callers need date/close only. Any supplied OHLCV columns are
    checked as well. Session completeness requires exchange metadata and is
    deliberately not inferred from a generic timestamp gap.
    """
    missing = {"date", "close"}.difference(prices.columns)
    if missing:
        raise ValueError(f"prices is missing required columns: {sorted(missing)}")
    if prices.empty:
        raise ValueError("not enough data: prices contains no rows")
    df = prices.copy()
    try:
        df["date"] = pd.to_datetime(df["date"], errors="raise")
        # Accessing .dt rejects mixed timezone/object timestamps.
        _ = df["date"].dt.tz
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("dates must be valid timestamps with a consistent timezone") from exc
    if df["date"].isna().any() or df["date"].duplicated().any():
        raise ValueError("dates must be present and unique")
    for column in ("open", "high", "low", "close", "volume"):
        if column not in df:
            continue
        try:
            values = pd.to_numeric(df[column], errors="raise").astype(float)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{column} must be numeric") from exc
        valid_sign = values >= 0 if column == "volume" else values > 0
        if not (np.isfinite(values) & valid_sign).all():
            raise ValueError(f"{column} must be finite and {'nonnegative' if column == 'volume' else 'positive'}")
        df[column] = values
    if {"open", "high", "low"}.issubset(df.columns):
        if (df["low"] > df[["open", "close", "high"]].min(axis=1)).any() or (
            df["high"] < df[["open", "close", "low"]].max(axis=1)
        ).any():
            raise ValueError("OHLC prices must satisfy low <= open/close <= high")
    return df.sort_values("date").reset_index(drop=True)
