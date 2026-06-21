from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from alphanexus.metrics import summarize_performance
from alphanexus.strategies import StrategyConfig, generate_signals


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
    if df.empty:
        raise ValueError("not enough data to run this strategy")

    cash = float(config.starting_cash)
    shares = 0.0
    last_entry_cost = 0.0
    fee_rate = config.fee_bps / 10_000
    slippage_rate = config.slippage_bps / 10_000
    portfolio_values: list[float] = []
    cash_values: list[float] = []
    share_values: list[float] = []
    realized_pnls: list[float] = []
    executed_signals: list[int] = []

    for _, row in df.iterrows():
        price = float(row["close"])
        trade_signal = int(row["trade_signal"])
        realized_pnl = 0.0
        executed_signal = 0

        if trade_signal > 0 and shares == 0:
            execution_price = price * (1 + slippage_rate)
            investable_cash = (cash * config.allocation) / (1 + fee_rate)
            shares = investable_cash / execution_price
            fee = investable_cash * fee_rate
            cash -= investable_cash + fee
            last_entry_cost = investable_cash + fee
            executed_signal = 1

        elif trade_signal < 0 and shares > 0:
            execution_price = price * (1 - slippage_rate)
            proceeds = shares * execution_price
            fee = proceeds * fee_rate
            cash += proceeds - fee
            realized_pnl = proceeds - fee - last_entry_cost
            shares = 0.0
            last_entry_cost = 0.0
            executed_signal = -1

        portfolio_value = cash + shares * price
        portfolio_values.append(portfolio_value)
        cash_values.append(cash)
        share_values.append(shares)
        realized_pnls.append(realized_pnl)
        executed_signals.append(executed_signal)

    df["trade_signal"] = executed_signals
    df["cash"] = cash_values
    df["shares"] = share_values
    df["realized_pnl"] = realized_pnls
    df["portfolio_value"] = portfolio_values
    df["strategy_return"] = df["portfolio_value"].pct_change().fillna(0)
    df["benchmark_value"] = config.starting_cash * (df["close"] / float(df["close"].iloc[0]))
    df["benchmark_return"] = df["benchmark_value"].pct_change().fillna(0)
    df["drawdown"] = df["portfolio_value"] / df["portfolio_value"].cummax() - 1

    metrics = summarize_performance(df, config.interval)
    return df, metrics
