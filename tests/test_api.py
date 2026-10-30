"""API-layer tests.

These exercise the HTTP contract rather than the maths: validation, status
codes, serialization shape, and the persistence round trip. The market-data
call is stubbed out so the suite never touches the network and never depends
on what a provider happens to be serving today.
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from alphanexus.data import MarketDataUnavailable
from api.limits import BacktestLimiter
from api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client whose run history lives in a throwaway database."""
    monkeypatch.setenv("DATABASE_PATH", os.path.join(tmp_path, "test_api.db"))
    # Reset directly. Some tests also replace this process-local limiter, and
    # stacking monkeypatch.setattr on the same State key can delete it twice
    # during fixture teardown on the CI Starlette version.
    app.state.backtest_limiter = BacktestLimiter()
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


@pytest.mark.parametrize("slippage", [10_000, 15_000])
def test_excessive_slippage_is_rejected(client, slippage):
    assert client.post("/backtests", json=valid_request(slippage_bps=slippage)).status_code == 422


def test_non_positive_starting_cash_is_rejected(client):
    response = client.post("/backtests", json=valid_request(starting_cash=0))

    assert response.status_code == 422


@pytest.mark.parametrize("patch,status", [
    ({"fee_bps": 20000}, 422), ({"slippage_bps": 1001}, 422),
    ({"starting_cash": 1e13}, 422), ({"slow_window": 10001}, 422),
    ({"fee_bps": "NaN"}, 422), ({"starting_cash": "Infinity"}, 422),
    ({"fast_window": 50, "slow_window": 20}, 400),
    ({"strategy": "rsi_mean_reversion", "oversold": 80, "overbought": 20}, 400),
])
def test_invalid_configuration_is_rejected_before_download(client, monkeypatch, patch, status):
    def unexpected(*args, **kwargs):
        pytest.fail("invalid configuration triggered a download")

    monkeypatch.setattr("api.main.fetch_prices", unexpected)
    assert client.post("/backtests?save=false", json=valid_request(**patch)).status_code == status


def test_api_ledger_can_reconcile_every_execution(client, stub_market_data):
    body = client.post("/backtests?save=false", json=valid_request(fee_bps=100, slippage_bps=100)).json()
    trades = body["trades"]
    assert len(trades) >= 2
    for trade in trades:
        notional = trade["shares"] * trade["fill_price"]
        assert trade["cash"] == pytest.approx(
            trade["cash_before"] - trade["trade_signal"] * notional - trade["fee"], abs=1e-9,
        )
        assert trade["signal_date"] < trade["date"]
        assert trade["fill_price"] != trade["close"]


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
    assert set(body) == {"ticker", "strategy", "metrics", "equity_curve", "trades", "run_id", "saved", "save_warning"}

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


@pytest.mark.parametrize("ticker", ["BRK-B", "^GSPC", "BTC-USD", "EURUSD=X", "7203.T", "aapl"])
def test_single_symbol_formats_are_supported(client, stub_market_data, ticker):
    response = client.post("/backtests?save=false", json=valid_request(ticker=ticker))
    assert response.status_code == 200
    assert response.json()["ticker"] == ticker.upper()


@pytest.mark.parametrize("ticker", ["AAPL MSFT", "AAPL,MSFT", "AAPL\n", "../AAPL", "A" * 21])
def test_invalid_ticker_is_rejected_before_fetching(client, monkeypatch, ticker):
    def unexpected_fetch(*args, **kwargs):
        pytest.fail("invalid ticker reached market data")

    monkeypatch.setattr("api.main.fetch_prices", unexpected_fetch)
    assert client.post("/backtests", json=valid_request(ticker=ticker)).status_code == 422


def test_rate_limit_stops_provider_calls_and_applies_to_unsaved_runs(client, monkeypatch):
    app.state.backtest_limiter = BacktestLimiter(limit=1)
    calls = []

    def fetch(*args, **kwargs):
        calls.append(1)
        return trending_prices()

    monkeypatch.setattr("api.main.fetch_prices", fetch)
    assert client.post("/backtests?save=false", json=valid_request()).status_code == 200
    response = client.post("/backtests", json=valid_request(), headers={"X-Forwarded-For": "1.2.3.4"})
    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert len(calls) == 1
    assert client.get("/health").status_code == 200
    assert client.get("/backtests").json() == []


def test_default_cors_allows_the_dashboard_but_not_unrelated_vercel_apps(client):
    allowed = client.get("/health", headers={"Origin": "https://alpha-nexus-ashy.vercel.app"})
    denied = client.get("/health", headers={"Origin": "https://unrelated.vercel.app"})
    assert allowed.headers["access-control-allow-origin"] == "https://alpha-nexus-ashy.vercel.app"
    assert "access-control-allow-origin" not in denied.headers


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


def test_every_endpoint_documents_its_response_schema(client):
    # The frontend's types mirror these schemas, so an endpoint that returns an
    # untyped dict would leave the OpenAPI docs, and anyone generating a client
    # from them, with nothing to go on.
    paths = client.get("/openapi.json").json()["paths"]

    for path, method in [("/strategies", "get"), ("/backtests", "get"), ("/backtests", "post")]:
        schema = paths[path][method]["responses"]["200"]["content"]["application/json"]["schema"]
        target = schema.get("items", schema)
        assert "$ref" in target, f"{method.upper()} {path} has no response model"


def test_history_rows_have_the_documented_fields(client, stub_market_data):
    client.post("/backtests", json=valid_request())

    (row,) = client.get("/backtests").json()

    assert set(row) == {
        "id",
        "created_at",
        "ticker",
        "strategy",
        "start_date",
        "end_date",
        "interval",
        "total_return",
        "benchmark_return",
        "sharpe_ratio",
        "max_drawdown",
        "trade_count",
        "has_snapshot",
    }


def test_a_run_with_save_false_is_not_persisted(client, stub_market_data):
    # The dashboard's automatic first-load run uses this so every visitor does
    # not add an identical AAPL row to the shared history.
    response = client.post("/backtests", params={"save": "false"}, json=valid_request())

    assert response.status_code == 200
    assert client.get("/backtests").json() == []


def test_runs_are_persisted_by_default(client, stub_market_data):
    client.post("/backtests", json=valid_request())

    assert len(client.get("/backtests").json()) == 1


def test_api_version_matches_the_project_version():
    # The version is written in three places (pyproject.toml, this API, and
    # frontend/package.json). They drifted once: v1.0.0 was released while all
    # three still said 0.1.0. This keeps them in step.
    import json
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    project_version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    frontend_version = json.loads((root / "frontend" / "package.json").read_text())["version"]

    assert app.version == project_version
    assert frontend_version == project_version


def test_saved_experiment_reopens_and_replays_after_process_restart(client, stub_market_data):
    posted = client.post("/backtests", json=valid_request(fee_bps=83, allocation=0.6)).json()
    assert posted["saved"] and posted["run_id"] is not None
    run_id = posted["run_id"]
    # A fresh interpreter cannot use the parent's cache or initialized DB state.
    code = """
import json, sys
from fastapi.testclient import TestClient
import api.main as api
def forbidden(*args, **kwargs):
    raise AssertionError('replay downloaded market data')
api.fetch_prices = forbidden
client = TestClient(api.app)
opened = client.get('/backtests/' + sys.argv[1])
replayed = client.post('/backtests/' + sys.argv[1] + '/replay')
print(json.dumps({'open_status': opened.status_code, 'opened': opened.json(),
                  'replay_status': replayed.status_code, 'replayed': replayed.json()}))
"""
    output = subprocess.run([sys.executable, "-c", code, str(run_id)], check=True, capture_output=True, text=True)
    check = json.loads(output.stdout)
    assert check["open_status"] == check["replay_status"] == 200
    assert check["opened"]["snapshot"]["request"]["fee_bps"] == 83
    assert check["opened"]["snapshot"]["result"] == posted
    assert check["replayed"]["matches"] is True
    assert check["replayed"]["result"]["trades"] == posted["trades"]
    assert len(client.get("/backtests").json()) == 1  # replay is read-only


def test_replay_survives_hourly_daylight_saving_offsets(client, monkeypatch):
    prices = trending_prices()
    prices["date"] = pd.date_range("2024-03-09", periods=len(prices), freq="h", tz="America/New_York")
    monkeypatch.setattr("api.main.fetch_prices", lambda *args: prices)
    saved = client.post("/backtests", json=valid_request(interval="1h")).json()
    replay = client.post(f"/backtests/{saved['run_id']}/replay")
    assert replay.status_code == 200
    assert replay.json()["matches"]


def test_failed_save_returns_result_and_an_explicit_warning(client, stub_market_data, monkeypatch):
    def fail(**kwargs):
        raise sqlite3.OperationalError("locked")

    monkeypatch.setattr("api.main.save_run", fail)
    response = client.post("/backtests", json=valid_request())
    assert response.status_code == 200
    body = response.json()
    assert body["equity_curve"] and not body["saved"]
    assert body["run_id"] is None
    assert "not saved" in body["save_warning"]


def test_missing_and_legacy_experiments_are_distinguished(client):
    from alphanexus.storage import save_run

    run_id = save_run("AAPL", "sma_crossover", "2024-01-01", "2024-06-01", "1d", {
        "total_return": 0, "benchmark_return": 0, "sharpe_ratio": 0, "max_drawdown": 0, "trade_count": 0,
    })
    assert client.get(f"/backtests/{run_id}").status_code == 409
    assert client.post(f"/backtests/{run_id}/replay").status_code == 409
    assert client.get("/backtests/9999").status_code == 404
    assert not client.get("/backtests").json()[0]["has_snapshot"]


def test_replay_rejects_corrupted_prices_and_reports_changed_results(client, stub_market_data):
    from alphanexus import storage

    saved = client.post("/backtests", json=valid_request()).json()
    run_id = saved["run_id"]
    snapshot = storage.get_experiment(run_id)["snapshot"]
    snapshot["result"]["metrics"]["ending_equity"] += 1
    with storage._connect() as connection:
        connection.execute("UPDATE experiments SET snapshot_json = ? WHERE run_id = ?", (json.dumps(snapshot), run_id))
    assert client.post(f"/backtests/{run_id}/replay").json()["matches"] is False
    snapshot["dataset"]["rows"][0]["close"] += 1
    with storage._connect() as connection:
        connection.execute("UPDATE experiments SET snapshot_json = ? WHERE run_id = ?", (json.dumps(snapshot), run_id))
    response = client.post(f"/backtests/{run_id}/replay")
    assert response.status_code == 409
    assert "integrity" in response.json()["detail"]


def test_replays_share_the_backtest_rate_limit(client, stub_market_data, monkeypatch):
    saved = client.post("/backtests", json=valid_request()).json()
    app.state.backtest_limiter = BacktestLimiter(limit=1)
    assert client.post(f"/backtests/{saved['run_id']}/replay").status_code == 200
    assert client.post(f"/backtests/{saved['run_id']}/replay").status_code == 429


def test_unavailable_history_is_a_service_error(client, monkeypatch):
    def fail(*args):
        raise sqlite3.OperationalError("read failure")

    monkeypatch.setattr("api.main.recent_runs", fail)
    monkeypatch.setattr("api.main.get_experiment", fail)
    assert client.get("/backtests").status_code == 503
    assert client.get("/backtests/1").status_code == 503
