from __future__ import annotations

from datetime import date
import time

import pandas as pd
import yfinance as yf


REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]

# How long a downloaded window stays reusable, and how many windows we keep.
# A closed historical window never changes, but a request whose end date is
# today keeps growing as bars print, so entries expire rather than pinning
# stale data forever. Fifteen minutes is well inside a daily bar and short
# enough that an intraday run is not meaningfully behind.
CACHE_TTL_SECONDS = 900
CACHE_MAX_ENTRIES = 32

_cache: dict[tuple[str, str, str, str], tuple[float, pd.DataFrame]] = {}


class MarketDataUnavailable(RuntimeError):
    """The upstream provider could not be reached or refused the request.

    Deliberately not a ValueError. A malformed request is the caller's fault
    and deserves a 4xx, but a provider outage or rate limit is an upstream
    failure the caller can do nothing about, so the API reports it as a 502.
    """


def clear_cache() -> None:
    """Drop every cached window. Used by tests and safe to call anytime."""
    _cache.clear()


def _cache_get(key: tuple[str, str, str, str]) -> pd.DataFrame | None:
    entry = _cache.get(key)
    if entry is None:
        return None

    stored_at, prices = entry
    if time.monotonic() - stored_at > CACHE_TTL_SECONDS:
        del _cache[key]
        return None

    return prices


def _cache_put(key: tuple[str, str, str, str], prices: pd.DataFrame) -> None:
    # Bounded so a long-lived server cannot accumulate frames without limit.
    # Insertion order is preserved by dict, so the first key is the oldest.
    if len(_cache) >= CACHE_MAX_ENTRIES:
        del _cache[next(iter(_cache))]
    _cache[key] = (time.monotonic(), prices)


def normalize_prices(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        raise ValueError("market data provider returned no rows")

    df = raw.copy().reset_index()
    df.columns = [str(column).lower().replace(" ", "_") for column in df.columns]
    if "datetime" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"datetime": "date"})
    if "adj_close" in df.columns and "close" not in df.columns:
        df = df.rename(columns={"adj_close": "close"})

    missing = set(REQUIRED_COLUMNS).difference(df.columns)
    if missing:
        raise ValueError(f"market data missing required columns: {sorted(missing)}")

    return df[REQUIRED_COLUMNS].dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)


def fetch_prices(
    ticker: str,
    start: date | str,
    end: date | str,
    interval: str = "1d",
) -> pd.DataFrame:
    key = (ticker.upper(), str(start), str(end), interval)

    cached = _cache_get(key)
    if cached is not None:
        # Hand back a copy so a caller mutating its frame cannot corrupt the
        # cache for everyone else.
        return cached.copy()

    try:
        raw = yf.download(
            ticker,
            start=str(start),
            end=str(end),
            interval=interval,
            auto_adjust=False,
            progress=False,
            multi_level_index=False,
        )
    except Exception as exc:  # noqa: BLE001 - any provider failure is upstream
        # yfinance surfaces network errors, rate limits and HTML error pages as
        # a variety of exception types, so the type is not worth branching on.
        raise MarketDataUnavailable(
            f"could not load market data for {ticker.upper()} from the upstream provider"
        ) from exc

    # Left outside the try on purpose: a ValueError here means the request was
    # bad (unknown ticker, range with no trading days), not that the provider
    # broke, and it should stay a 400.
    prices = normalize_prices(raw)

    _cache_put(key, prices)
    return prices.copy()
