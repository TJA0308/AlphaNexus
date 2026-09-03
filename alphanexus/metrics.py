from __future__ import annotations

import math

import pandas as pd


def annualization_factor(interval: str) -> float:
    mapping = {
        "1d": 252,
        "1h": 252 * 6.5,
        "30m": 252 * 13,
        "15m": 252 * 26,
    }
    return mapping.get(interval, 252)


def max_drawdown(equity_curve: pd.Series) -> float:
    peak = equity_curve.cummax()
    drawdown = equity_curve / peak - 1
    return float(drawdown.min())


def sharpe_ratio(returns: pd.Series, interval: str = "1d", risk_free_rate: float = 0.0) -> float:
    clean_returns = returns.dropna()
    if clean_returns.empty or clean_returns.std() == 0:
        return 0.0

    period_rf = risk_free_rate / annualization_factor(interval)
    excess = clean_returns - period_rf
    return float((excess.mean() / excess.std()) * math.sqrt(annualization_factor(interval)))


def summarize_performance(result: pd.DataFrame, interval: str = "1d") -> dict[str, float | int]:
    if result.empty:
        raise ValueError("result cannot be empty")

    starting_equity = float(result["portfolio_value"].iloc[0])
    ending_equity = float(result["portfolio_value"].iloc[-1])
    starting_benchmark = float(result["benchmark_value"].iloc[0])
    ending_benchmark = float(result["benchmark_value"].iloc[-1])
    # Both trade_count and win_rate are measured on *exits*, so one round trip
    # counts once rather than twice. A position still open on the final bar has
    # no realized PnL yet and is therefore excluded from both, even though its
    # unrealized value is still reflected in ending_equity.
    completed_trades = result[result["trade_signal"] != 0]
    profitable_exits = completed_trades[
        (completed_trades["trade_signal"] < 0) & (completed_trades["realized_pnl"] > 0)
    ]
    exits = completed_trades[completed_trades["trade_signal"] < 0]

    total_return = ending_equity / starting_equity - 1
    benchmark_return = ending_benchmark / starting_benchmark - 1

    return {
        "total_return": total_return,
        "benchmark_return": benchmark_return,
        # Deliberately *not* called alpha. Alpha is the intercept of a
        # regression of strategy returns on benchmark returns, which requires
        # estimating beta and adjusting for the risk taken to earn the excess.
        # This is the simpler quantity: raw return difference over the window,
        # with no risk adjustment. Naming it alpha would overstate it.
        "excess_return_vs_benchmark": total_return - benchmark_return,
        "max_drawdown": max_drawdown(result["portfolio_value"]),
        "sharpe_ratio": sharpe_ratio(result["strategy_return"], interval),
        "trade_count": int(len(exits)),
        "win_rate": float(len(profitable_exits) / len(exits)) if len(exits) else 0.0,
        "ending_equity": ending_equity,
    }

