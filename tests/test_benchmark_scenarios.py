import math

from alphanexus.backtest import run_backtest
from benchmarks.scenarios import (
    DATE_WINDOWS,
    FIXTURE_ASSETS,
    STRATEGIES,
    iter_scenarios,
    load_fixture,
    load_prices_for_scenario,
)


def test_benchmark_fixtures_have_expected_ohlcv_schema():
    expected_columns = ["date", "open", "high", "low", "close", "volume"]

    for asset in FIXTURE_ASSETS:
        prices = load_fixture(asset)

        assert list(prices.columns) == expected_columns
        assert len(prices) >= 500
        assert prices["close"].gt(0).all()


def test_backtest_scenario_matrix_completes_successfully():
    scenarios = list(iter_scenarios())
    expected_count = len(FIXTURE_ASSETS) * len(DATE_WINDOWS) * len(STRATEGIES)

    assert len(scenarios) == expected_count == 72

    for scenario in scenarios:
        prices = load_prices_for_scenario(scenario)
        result, metrics = run_backtest(prices, scenario.strategy_config, scenario.backtest_config)

        assert not result.empty, scenario.id
        assert result["portfolio_value"].gt(0).all(), scenario.id
        assert math.isfinite(float(metrics["ending_equity"])), scenario.id
        assert math.isfinite(float(metrics["total_return"])), scenario.id
        assert math.isfinite(float(metrics["max_drawdown"])), scenario.id
        assert int(metrics["trade_count"]) >= 0, scenario.id
