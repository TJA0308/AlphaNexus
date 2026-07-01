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


def test_signals_are_lagged_to_avoid_lookahead_bias():
    # The fast SMA (window 2) first rises above the slow SMA (window 5) on the
    # bar where price jumps to 11. Without lagging, the buy would execute on
    # that same bar's close. With the one-bar lag it must execute on the
    # *following* bar instead, proving we never trade on a close we just saw.
    from alphanexus.strategies import StrategyConfig, generate_signals

    signals = generate_signals(
        sample_prices(),
        StrategyConfig(name="sma_crossover", fast_window=2, slow_window=5),
    )

    # Find the first bar whose own SMAs cross long, then confirm the buy
    # (trade_signal == 1) lands on the next bar, not that one.
    crossover_bar = (signals["fast_sma"] > signals["slow_sma"]).idxmax()
    assert signals.loc[crossover_bar, "trade_signal"] == 0
    assert signals.loc[crossover_bar + 1, "trade_signal"] == 1


def test_backtest_records_executed_trades_only_when_position_changes():
    result, _ = run_backtest(
        sample_prices(),
        StrategyConfig(name="sma_crossover", fast_window=2, slow_window=5),
        BacktestConfig(starting_cash=10_000, fee_bps=0, slippage_bps=0),
    )

    trades = result[result["trade_signal"] != 0]

    assert set(trades["trade_signal"]).issubset({-1, 1})
    assert len(trades) <= 2


def test_trade_quantity_records_shares_bought_and_sold():
    result, _ = run_backtest(
        sample_prices(),
        StrategyConfig(name="sma_crossover", fast_window=2, slow_window=5),
        BacktestConfig(starting_cash=10_000, fee_bps=0, slippage_bps=0),
    )

    trades = result[result["trade_signal"] != 0]

    assert list(trades["trade_signal"]) == [1, -1]
    assert trades["trade_shares"].gt(0).all()
    assert trades.iloc[0]["trade_shares"] == trades.iloc[1]["trade_shares"]
    assert trades.iloc[1]["shares"] == 0
