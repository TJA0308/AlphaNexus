from __future__ import annotations

import re
import time
from datetime import date
from threading import Lock

import pandas as pd
import yfinance as yf

from alphanexus.validation import validate_prices

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]

# How long a downloaded window stays reusable, and how many windows we keep.
# Historical windows can be revised and current windows keep growing.
# Expiry bounds cache staleness; it does not establish bar completeness.
CACHE_TTL_SECONDS = 900
CACHE_MAX_ENTRIES = 32

_cache: dict[tuple[str, str, str, str], tuple[float, pd.DataFrame]] = {}
_cache_lock = Lock()
TICKER_PATTERN = r"^[A-Za-z0-9^][A-Za-z0-9.^=-]{0,19}$"


class MarketDataUnavailable(RuntimeError):
    """The upstream provider could not be reached or refused the request.

    Deliberately not a ValueError. A malformed request is the caller's fault
    and deserves a 4xx, but a provider outage or rate limit is an upstream
    failure the caller can do nothing about, so the API reports it as a 502.
    """


def clear_cache() -> None:
    """Drop every cached window. Used by tests and safe to call anytime."""
    with _cache_lock:
        _cache.clear()


def _cache_get(key: tuple[str, str, str, str]) -> pd.DataFrame | None:
    with _cache_lock:
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
    with _cache_lock:
        if key not in _cache and len(_cache) >= CACHE_MAX_ENTRIES:
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

    return validate_prices(df[REQUIRED_COLUMNS])


def _inclusive_end(end: date | str) -> str:
    """yfinance's `end` is exclusive; push it a day so the chosen end date is included."""
    return str((pd.Timestamp(end) + pd.Timedelta(days=1)).date())


def fetch_prices(
    ticker: str,
    start: date | str,
    end: date | str,
    interval: str = "1d",
) -> pd.DataFrame:
    if not re.fullmatch(TICKER_PATTERN, ticker):
        raise ValueError("enter one ticker using letters, numbers, or . - ^ =")
    ticker = ticker.upper()
    key = (ticker, str(start), str(end), interval)

    cached = _cache_get(key)
    if cached is not None:
        # Hand back a copy so a caller mutating its frame cannot corrupt the
        # cache for everyone else.
        return cached.copy()

    try:
        raw = yf.download(
            ticker,
            start=str(start),
            end=_inclusive_end(end),
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

    # download() can swallow provider exceptions and return an empty frame.
    # With no structured cause we cannot blame the caller or assert an outage.
    if raw.empty:
        raise MarketDataUnavailable(
            f"no {interval} price data available for {ticker.upper()} between {start} and {end}; "
            "the provider did not establish whether the symbol/range is unavailable or a download failed. "
            "Check the symbol and range, or retry later (hourly history is limited)."
        )
    try:
        prices = normalize_prices(raw)
    except ValueError as exc:
        raise MarketDataUnavailable(f"invalid market data for {ticker}: {exc}") from exc

    _cache_put(key, prices)
    return prices.copy()
