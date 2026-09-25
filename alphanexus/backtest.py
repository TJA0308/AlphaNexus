from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alphanexus.metrics import summarize_performance
from alphanexus.strategies import StrategyConfig, generate_signals, warmup_bars


@dataclass(frozen=True)
class BacktestConfig:
    starting_cash: float = 10_000.0
    fee_bps: float = 5.0
    slippage_bps: float = 5.0
    allocation: float = 1.0
    interval: str = "1d"


def run_backtest(
    prices: pd.DataFrame,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    config = backtest_config or BacktestConfig()
    if config.starting_cash <= 0:
        raise ValueError("starting_cash must be greater than 0")
    if not 0 < config.allocation <= 1:
        raise ValueError("allocation must be between 0 and 1")

    df = generate_signals(prices, strategy_config).dropna(subset=["close"]).reset_index(drop=True)
    # Refuse a window too short for the indicators to warm up. Without this the
    # SMAs stay NaN, the signal is flat, and the run reports a confident 0.00%
    # return that is indistinguishable from a strategy that was genuinely
    # tested and chose not to trade.
    required_bars = warmup_bars(strategy_config)
    if len(df) < required_bars:
        raise ValueError(
            f"not enough data to run this strategy: {len(df)} bars available, "
            f"{required_bars} needed before it can hold a position"
        )

    fee_rate = config.fee_bps / 10_000
    slippage_rate = config.slippage_bps / 10_000

    # The simulation is inherently sequential (each trade's size depends on the
    # cash left by the previous one), so it stays a loop. It iterates over plain
    # NumPy arrays rather than df.iterrows(): iterrows builds a pandas Series for
    # every row, which made that per-row overhead the dominant cost of a run.
    closes = df["close"].to_numpy(dtype=float)
    trade_signals = df["trade_signal"].to_numpy(dtype=int)
    bars = len(df)

    portfolio_values = np.empty(bars)
    cash_values = np.empty(bars)
    share_values = np.empty(bars)
    realized_pnls = np.zeros(bars)
    executed_signals = np.zeros(bars, dtype=int)
    executed_share_values = np.zeros(bars)

    cash = float(config.starting_cash)
    shares = 0.0
    last_entry_cost = 0.0

    for i in range(bars):
        price = closes[i]
        trade_signal = trade_signals[i]

        if trade_signal > 0 and shares == 0:
            execution_price = price * (1 + slippage_rate)
            # Split the amount spent into position and fee, then subtract the
            # amount itself. Rebuilding it as position + fee rounds differently
            # and leaves residue like -1.8e-12 behind a full-allocation entry.
            spent = cash * config.allocation
            investable_cash = spent / (1 + fee_rate)
            fee = spent - investable_cash
            shares = investable_cash / execution_price
            cash -= spent
            last_entry_cost = spent
            executed_signals[i] = 1
            executed_share_values[i] = shares

        elif trade_signal < 0 and shares > 0:
            execution_price = price * (1 - slippage_rate)
            executed_share_values[i] = shares
            proceeds = shares * execution_price
            fee = proceeds * fee_rate
            cash += proceeds - fee
            realized_pnls[i] = proceeds - fee - last_entry_cost
            shares = 0.0
            last_entry_cost = 0.0
            executed_signals[i] = -1

        portfolio_values[i] = cash + shares * price
        cash_values[i] = cash
        share_values[i] = shares

    df["trade_signal"] = executed_signals
    df["trade_shares"] = executed_share_values
    df["cash"] = cash_values
    df["shares"] = share_values
    df["realized_pnl"] = realized_pnls
    df["portfolio_value"] = portfolio_values
    # The first bar has no prior bar to compare against, so its return is
    # genuinely undefined rather than zero. We leave the NaN in place: filling
    # it with 0 would feed a fabricated flat day into the Sharpe calculation,
    # which drags the standard deviation and the mean toward zero. Consumers
    # that need a number (the metrics layer) drop it explicitly.
    df["strategy_return"] = df["portfolio_value"].pct_change()
    df["benchmark_value"] = config.starting_cash * (df["close"] / float(df["close"].iloc[0]))
    df["benchmark_return"] = df["benchmark_value"].pct_change()
    df["drawdown"] = df["portfolio_value"] / df["portfolio_value"].cummax() - 1

    metrics = summarize_performance(df, config.interval)
    return df, metrics
