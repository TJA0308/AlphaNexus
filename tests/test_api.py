"""API-layer tests.

These exercise the HTTP contract rather than the maths: validation, status
codes, serialization shape, and the persistence round trip. The market-data
call is stubbed out so the suite never touches the network and never depends
on what a provider happens to be serving today.
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from alphanexus.data import MarketDataUnavailable
from api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client whose run history lives in a throwaway database."""
    monkeypatch.setenv("DATABASE_PATH", os.path.join(tmp_path, "test_api.db"))
    return TestClient(app)


def trending_prices(rows: int = 60) -> pd.DataFrame:
    """A price path that rises then falls, so strategies actually trade."""
    start = datetime(2024, 1, 1)
    half = rows // 2
    close = [10.0 + index for index in range(half)]
    close += [close[-1] - index for index in range(rows - half)]
    return pd.DataFrame(
        {
            "date": [start + timedelta(days=index) for index in range(rows)],
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": [1_000] * rows,
        }
    )


@pytest.fixture
def stub_market_data(monkeypatch):
    """Replace the provider call so tests are offline and deterministic."""

    def fake_fetch_prices(ticker, start, end, interval="1d"):
        return trending_prices()

    monkeypatch.setattr("api.main.fetch_prices", fake_fetch_prices)


def valid_request(**overrides) -> dict:
    payload = {
        "ticker": "AAPL",
        "start": "2024-01-01",
        "end": "2024-06-01",
        "interval": "1d",
        "strategy": "sma_crossover",
        "starting_cash": 10_000,
        "fee_bps": 5,
        "slippage_bps": 5,
        "allocation": 1,
        "fast_window": 5,
        "slow_window": 20,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# Read-only routes
# --------------------------------------------------------------------------


def test_health_reports_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_strategies_lists_every_supported_strategy(client):
    response = client.get("/strategies")

    assert response.status_code == 200
    ids = {strategy["id"] for strategy in response.json()}
    assert ids == {"sma_crossover", "rsi_mean_reversion", "bollinger_breakout"}


# --------------------------------------------------------------------------
# Request validation
# --------------------------------------------------------------------------


def test_start_on_or_after_end_is_rejected(client):
    response = client.post("/backtests", json=valid_request(start="2024-06-01", end="2024-01-01"))

    assert response.status_code == 400
    assert "before end date" in response.json()["detail"]


def test_equal_start_and_end_is_rejected(client):
    response = client.post("/backtests", json=valid_request(start="2024-01-01", end="2024-01-01"))

    assert response.status_code == 400


def test_unknown_strategy_is_rejected_by_the_schema(client):
    # Caught by the Literal on StrategyName before any engine code runs.
    response = client.post("/backtests", json=valid_request(strategy="buy_the_dip"))

    assert response.status_code == 422


def test_allocation_above_one_is_rejected(client):
    # Allocating more than the account is leverage, which this engine does not
    # model, so it must be refused at the edge rather than silently clamped.
    response = client.post("/backtests", json=valid_request(allocation=1.5))

    assert response.status_code == 422


def test_non_positive_starting_cash_is_rejected(client):
    response = client.post("/backtests", json=valid_request(starting_cash=0))

    assert response.status_code == 422


def test_engine_value_errors_become_400_not_500(client, stub_market_data):
    # fast_window >= slow_window raises ValueError deep in the strategy layer.
    # That is a bad request, not a server fault.
    response = client.post("/backtests", json=valid_request(fast_window=50, slow_window=20))

    assert response.status_code == 400
    assert "fast_window" in response.json()["detail"]


def test_a_provider_outage_becomes_502_not_400(client, monkeypatch):
    # The caller's request is fine; the upstream data provider is not. Reporting
    # this as a 400 would tell the user to fix a payload that has no problem.
    def unavailable(ticker, start, end, interval="1d"):
        raise MarketDataUnavailable("could not load market data for AAPL")

    monkeypatch.setattr("api.main.fetch_prices", unavailable)

    response = client.post("/backtests", json=valid_request())

    assert response.status_code == 502
    assert "market data" in response.json()["detail"]


def test_a_provider_outage_is_not_persisted(client, monkeypatch):
    def unavailable(ticker, start, end, interval="1d"):
        raise MarketDataUnavailable("provider down")

    monkeypatch.setattr("api.main.fetch_prices", unavailable)
    client.post("/backtests", json=valid_request())

    assert client.get("/backtests").json() == []


# --------------------------------------------------------------------------
# The history endpoint's limit bounds
# --------------------------------------------------------------------------


def test_negative_limit_is_rejected(client):
    # Regression test. SQLite reads a negative LIMIT as "no limit", so an
    # unvalidated ?limit=-1 used to return the entire runs table.
    response = client.get("/backtests", params={"limit": -1})

    assert response.status_code == 422


def test_zero_limit_is_rejected(client):
    response = client.get("/backtests", params={"limit": 0})

    assert response.status_code == 422


def test_limit_above_the_ceiling_is_rejected(client):
    response = client.get("/backtests", params={"limit": 101})

    assert response.status_code == 422


def test_limit_at_the_boundaries_is_accepted(client):
    assert client.get("/backtests", params={"limit": 1}).status_code == 200
    assert client.get("/backtests", params={"limit": 100}).status_code == 200


# --------------------------------------------------------------------------
# Response shape and persistence
# --------------------------------------------------------------------------


def test_successful_backtest_returns_the_documented_shape(client, stub_market_data):
    response = client.post("/backtests", json=valid_request())

    assert response.status_code == 200
    body = response.json()

    assert body["ticker"] == "AAPL"
    assert body["strategy"] == "sma_crossover"
    assert set(body) == {"ticker", "strategy", "metrics", "equity_curve", "trades"}

    expected_metrics = {
        "total_return",
        "benchmark_return",
        "excess_return_vs_benchmark",
        "max_drawdown",
        "sharpe_ratio",
        "trade_count",
        "win_rate",
        "ending_equity",
    }
    assert set(body["metrics"]) == expected_metrics

    assert len(body["equity_curve"]) > 0
    assert set(body["equity_curve"][0]) == {
        "date",
        "close",
        "portfolio_value",
        "benchmark_value",
        "drawdown",
        "signal",
        "trade_signal",
    }


def test_ticker_is_normalized_to_uppercase(client, stub_market_data):
    response = client.post("/backtests", json=valid_request(ticker="aapl"))

    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"


def test_every_returned_trade_is_an_actual_execution(client, stub_market_data):
    body = client.post("/backtests", json=valid_request()).json()

    assert len(body["trades"]) > 0
    for trade in body["trades"]:
        assert trade["trade_signal"] in (1, -1)
        assert trade["shares"] > 0


def test_running_a_backtest_persists_it_to_the_history(client, stub_market_data):
    assert client.get("/backtests").json() == []

    posted = client.post("/backtests", json=valid_request(ticker="msft")).json()
    history = client.get("/backtests").json()

    assert len(history) == 1
    saved = history[0]
    assert saved["ticker"] == "MSFT"
    assert saved["strategy"] == "sma_crossover"
    assert saved["start_date"] == "2024-01-01"
    assert saved["end_date"] == "2024-06-01"
    # The stored summary must agree with what the caller was told.
    assert saved["total_return"] == pytest.approx(posted["metrics"]["total_return"])
    assert saved["trade_count"] == posted["metrics"]["trade_count"]


def test_history_returns_newest_first(client, stub_market_data):
    client.post("/backtests", json=valid_request(ticker="aapl"))
    client.post("/backtests", json=valid_request(ticker="msft"))

    history = client.get("/backtests").json()

    assert [run["ticker"] for run in history] == ["MSFT", "AAPL"]


def test_a_rejected_backtest_is_not_persisted(client, stub_market_data):
    client.post("/backtests", json=valid_request(fast_window=50, slow_window=20))

    assert client.get("/backtests").json() == []
