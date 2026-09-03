"""Tests for market-data loading, caching, and provider failure handling.

The provider call is always stubbed. These tests assert how we behave around
yfinance, never that yfinance itself works.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from alphanexus import data
from alphanexus.data import MarketDataUnavailable, fetch_prices, normalize_prices


@pytest.fixture(autouse=True)
def empty_cache():
    """Every test starts and ends with a cold cache."""
    data.clear_cache()
    yield
    data.clear_cache()


def raw_provider_frame(rows: int = 5) -> pd.DataFrame:
    """Shaped like what yfinance returns: capitalised columns, date index."""
    index = pd.DatetimeIndex(
        [datetime(2024, 1, 1) + timedelta(days=offset) for offset in range(rows)],
        name="Date",
    )
    close = [10.0 + offset for offset in range(rows)]
    return pd.DataFrame(
        {
            "Open": close,
            "High": close,
            "Low": close,
            "Close": close,
            "Volume": [1_000] * rows,
        },
        index=index,
    )


# --------------------------------------------------------------------------
# normalize_prices
# --------------------------------------------------------------------------


def test_normalize_lowercases_columns_and_promotes_the_index():
    normalized = normalize_prices(raw_provider_frame())

    assert list(normalized.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(normalized) == 5


def test_normalize_rejects_an_empty_response():
    with pytest.raises(ValueError, match="no rows"):
        normalize_prices(pd.DataFrame())


def test_normalize_rejects_a_response_missing_required_columns():
    incomplete = raw_provider_frame().drop(columns=["Volume"])

    with pytest.raises(ValueError, match="missing required columns"):
        normalize_prices(incomplete)


def test_normalize_sorts_by_date():
    shuffled = raw_provider_frame().iloc[::-1]

    normalized = normalize_prices(shuffled)

    assert normalized["date"].is_monotonic_increasing


# --------------------------------------------------------------------------
# Provider failures
# --------------------------------------------------------------------------


def test_provider_exceptions_become_market_data_unavailable(monkeypatch):
    def exploding_download(*args, **kwargs):
        raise ConnectionError("connection reset by peer")

    monkeypatch.setattr(data.yf, "download", exploding_download)

    with pytest.raises(MarketDataUnavailable, match="AAPL"):
        fetch_prices("aapl", "2024-01-01", "2024-02-01")


def test_market_data_unavailable_is_not_a_value_error(monkeypatch):
    # The API distinguishes the two: ValueError is a 400, this is a 502. If it
    # ever became a ValueError subclass, provider outages would silently start
    # being reported as the caller's fault.
    assert not issubclass(MarketDataUnavailable, ValueError)


def test_an_empty_provider_response_stays_a_value_error(monkeypatch):
    # An unknown ticker or a range with no trading days is a bad request, so it
    # must not be swallowed into the provider-failure path.
    monkeypatch.setattr(data.yf, "download", lambda *args, **kwargs: pd.DataFrame())

    with pytest.raises(ValueError, match="no rows"):
        fetch_prices("NOPE", "2024-01-01", "2024-02-01")


def test_a_failed_fetch_is_not_cached(monkeypatch):
    calls = []

    def exploding_download(*args, **kwargs):
        calls.append(1)
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(data.yf, "download", exploding_download)

    for _ in range(2):
        with pytest.raises(MarketDataUnavailable):
            fetch_prices("AAPL", "2024-01-01", "2024-02-01")

    # A transient outage must not poison the cache into permanent failure.
    assert len(calls) == 2


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------


def counting_download(calls: list):
    def download(*args, **kwargs):
        calls.append(1)
        return raw_provider_frame()

    return download


def test_repeating_a_request_skips_the_network(monkeypatch):
    calls = []
    monkeypatch.setattr(data.yf, "download", counting_download(calls))

    first = fetch_prices("AAPL", "2024-01-01", "2024-02-01")
    second = fetch_prices("AAPL", "2024-01-01", "2024-02-01")

    assert len(calls) == 1
    pd.testing.assert_frame_equal(first, second)


def test_a_different_window_is_a_different_cache_entry(monkeypatch):
    calls = []
    monkeypatch.setattr(data.yf, "download", counting_download(calls))

    fetch_prices("AAPL", "2024-01-01", "2024-02-01")
    fetch_prices("AAPL", "2024-01-01", "2024-03-01")
    fetch_prices("MSFT", "2024-01-01", "2024-02-01")
    fetch_prices("AAPL", "2024-01-01", "2024-02-01", interval="1h")

    assert len(calls) == 4


def test_ticker_case_does_not_create_a_duplicate_entry(monkeypatch):
    calls = []
    monkeypatch.setattr(data.yf, "download", counting_download(calls))

    fetch_prices("aapl", "2024-01-01", "2024-02-01")
    fetch_prices("AAPL", "2024-01-01", "2024-02-01")

    assert len(calls) == 1


def test_callers_cannot_mutate_the_cached_frame(monkeypatch):
    calls = []
    monkeypatch.setattr(data.yf, "download", counting_download(calls))

    first = fetch_prices("AAPL", "2024-01-01", "2024-02-01")
    first.loc[0, "close"] = -999.0

    second = fetch_prices("AAPL", "2024-01-01", "2024-02-01")

    assert second.loc[0, "close"] != -999.0


def test_entries_expire_once_the_ttl_passes(monkeypatch):
    calls = []
    monkeypatch.setattr(data.yf, "download", counting_download(calls))

    clock = [1_000.0]
    monkeypatch.setattr(data.time, "monotonic", lambda: clock[0])

    fetch_prices("AAPL", "2024-01-01", "2024-02-01")
    # Still inside the window: served from cache.
    clock[0] += data.CACHE_TTL_SECONDS - 1
    fetch_prices("AAPL", "2024-01-01", "2024-02-01")
    assert len(calls) == 1

    # Past the window: refetched, because a range ending today keeps growing.
    clock[0] += 2
    fetch_prices("AAPL", "2024-01-01", "2024-02-01")
    assert len(calls) == 2


def test_the_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(data.yf, "download", lambda *args, **kwargs: raw_provider_frame())

    for offset in range(data.CACHE_MAX_ENTRIES + 10):
        fetch_prices("AAPL", "2024-01-01", f"2024-02-{offset % 28 + 1:02d}")

    assert len(data._cache) <= data.CACHE_MAX_ENTRIES
