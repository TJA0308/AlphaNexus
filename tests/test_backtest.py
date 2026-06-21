from datetime import datetime, timedelta

import pandas as pd

from alphanexus.backtest import BacktestConfig, run_backtest
from alphanexus.strategies import StrategyConfig


def sample_prices() -> pd.DataFrame:
    start = datetime(2024, 1, 1)
    close = [10, 10, 10, 10, 10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10]
    return pd.DataFrame(
        {
            "date": [start + timedelta(days=index) for index in range(len(close))],
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": [1000] * len(close),
        }
    )


def test_backtest_generates_metrics_and_never_loses_cash_to_negative_fee_bug():
    result, metrics = run_backtest(
        sample_prices(),
        StrategyConfig(name="sma_crossover", fast_window=2, slow_window=5),
        BacktestConfig(starting_cash=10_000, fee_bps=10, slippage_bps=0),
    )

    assert not result.empty
    assert result["cash"].min() >= -0.000001
    assert "total_return" in metrics
    assert "max_drawdown" in metrics
    assert "sharpe_ratio" in metrics


def test_backtest_records_executed_trades_only_when_position_changes():
    result, _ = run_backtest(
        sample_prices(),
        StrategyConfig(name="sma_crossover", fast_window=2, slow_window=5),
        BacktestConfig(starting_cash=10_000, fee_bps=0, slippage_bps=0),
    )

    trades = result[result["trade_signal"] != 0]

    assert set(trades["trade_signal"]).issubset({-1, 1})
    assert len(trades) <= 2
