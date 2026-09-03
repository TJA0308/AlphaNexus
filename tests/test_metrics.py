"""Known-answer tests for the metrics layer.

Every expected value here is computed by hand in the comments rather than
captured from a previous run, so a change in behaviour shows up as a failing
assertion instead of silently becoming the new baseline.
"""

import math

import pandas as pd
import pytest

from alphanexus.metrics import (
    annualization_factor,
    max_drawdown,
    sharpe_ratio,
    summarize_performance,
)


# --------------------------------------------------------------------------
# annualization_factor
# --------------------------------------------------------------------------


def test_annualization_factor_known_intervals():
    assert annualization_factor("1d") == 252
    assert annualization_factor("1h") == 252 * 6.5
    assert annualization_factor("30m") == 252 * 13
    assert annualization_factor("15m") == 252 * 26


def test_annualization_factor_falls_back_to_daily_for_unknown_interval():
    # An unrecognised interval must not raise mid-backtest; daily is the
    # conservative default because it produces the smallest scaling factor.
    assert annualization_factor("1w") == 252


# --------------------------------------------------------------------------
# max_drawdown
# --------------------------------------------------------------------------


def test_max_drawdown_measures_peak_to_trough():
    # Peak is 120, the trough after it is 90, so the worst drawdown is
    # 90 / 120 - 1 = -0.25. The later recovery to 110 must not shrink it.
    equity = pd.Series([100.0, 120.0, 90.0, 110.0])
    assert max_drawdown(equity) == pytest.approx(-0.25)


def test_max_drawdown_is_zero_for_a_curve_that_never_falls():
    equity = pd.Series([100.0, 101.0, 105.0, 130.0])
    assert max_drawdown(equity) == pytest.approx(0.0)


def test_max_drawdown_uses_the_deepest_trough_not_the_last_one():
    # Two separate drawdowns: 60/100 - 1 = -0.40, then 150/200 - 1 = -0.25.
    # The function must report the deeper one even though it happened first.
    equity = pd.Series([100.0, 60.0, 200.0, 150.0])
    assert max_drawdown(equity) == pytest.approx(-0.40)


# --------------------------------------------------------------------------
# sharpe_ratio
# --------------------------------------------------------------------------


def test_sharpe_ratio_matches_hand_calculation():
    # returns = [0.01, 0.02, 0.03]
    #   mean = 0.02
    #   sample std (ddof=1) = 0.01
    #   ratio = 0.02 / 0.01 = 2.0
    #   annualised = 2.0 * sqrt(252)
    returns = pd.Series([0.01, 0.02, 0.03])
    assert sharpe_ratio(returns) == pytest.approx(2.0 * math.sqrt(252))


def test_sharpe_ratio_scales_with_the_interval():
    # The same returns sampled hourly annualise by sqrt(252 * 6.5) instead.
    returns = pd.Series([0.01, 0.02, 0.03])
    assert sharpe_ratio(returns, interval="1h") == pytest.approx(2.0 * math.sqrt(252 * 6.5))


def test_sharpe_ratio_subtracts_the_risk_free_rate():
    # A 2% annual risk-free rate is de-annualised to 0.02 / 252 per bar and
    # subtracted from every return, which lowers the mean but leaves the
    # standard deviation unchanged (subtracting a constant does not disperse).
    returns = pd.Series([0.01, 0.02, 0.03])
    period_rf = 0.02 / 252
    expected = ((0.02 - period_rf) / 0.01) * math.sqrt(252)
    assert sharpe_ratio(returns, risk_free_rate=0.02) == pytest.approx(expected)


def test_sharpe_ratio_returns_zero_when_returns_never_vary():
    # Zero standard deviation would divide by zero. A flat return stream has
    # no risk to reward, so 0.0 is the honest answer rather than infinity.
    returns = pd.Series([0.01, 0.01, 0.01, 0.01])
    assert sharpe_ratio(returns) == 0.0


def test_sharpe_ratio_returns_zero_for_an_empty_series():
    assert sharpe_ratio(pd.Series([], dtype=float)) == 0.0


def test_sharpe_ratio_ignores_the_undefined_first_bar():
    # The engine leaves bar 0 as NaN because there is no prior bar to compare
    # against. Dropping it must give exactly the same answer as a series that
    # never had it, which is what stops a fabricated flat day from deflating
    # both the mean and the standard deviation.
    with_leading_nan = pd.Series([float("nan"), 0.01, 0.02, 0.03])
    without = pd.Series([0.01, 0.02, 0.03])
    assert sharpe_ratio(with_leading_nan) == pytest.approx(sharpe_ratio(without))


def test_sharpe_ratio_would_differ_if_the_first_bar_were_filled_with_zero():
    # Guards the fix directly: filling bar 0 with 0.0 is not a no-op, it moves
    # the number. If someone reintroduces .fillna(0) upstream, this documents
    # what it costs.
    honest = pd.Series([float("nan"), 0.01, 0.02, 0.03])
    fabricated = pd.Series([0.0, 0.01, 0.02, 0.03])
    assert sharpe_ratio(honest) != pytest.approx(sharpe_ratio(fabricated))


# --------------------------------------------------------------------------
# summarize_performance
# --------------------------------------------------------------------------


def performance_frame(
    trade_signal: list[int],
    realized_pnl: list[float],
) -> pd.DataFrame:
    """Build a minimal result frame with a known equity and benchmark path."""
    portfolio_value = [10_000.0, 10_500.0, 10_200.0, 11_000.0, 10_800.0, 11_500.0]
    benchmark_value = [10_000.0, 10_100.0, 10_050.0, 10_200.0, 10_150.0, 10_300.0]
    frame = pd.DataFrame(
        {
            "portfolio_value": portfolio_value,
            "benchmark_value": benchmark_value,
            "trade_signal": trade_signal,
            "realized_pnl": realized_pnl,
        }
    )
    # Mirrors the engine: bar 0 is NaN, not 0.
    frame["strategy_return"] = frame["portfolio_value"].pct_change()
    return frame


def test_summarize_performance_returns_and_excess():
    result = performance_frame(
        trade_signal=[1, 0, -1, 1, 0, -1],
        realized_pnl=[0.0, 0.0, 200.0, 0.0, 0.0, -50.0],
    )
    metrics = summarize_performance(result)

    # 11500 / 10000 - 1 = 0.15
    assert metrics["total_return"] == pytest.approx(0.15)
    # 10300 / 10000 - 1 = 0.03
    assert metrics["benchmark_return"] == pytest.approx(0.03)
    # 0.15 - 0.03 = 0.12
    assert metrics["excess_return_vs_benchmark"] == pytest.approx(0.12)
    assert metrics["ending_equity"] == pytest.approx(11_500.0)


def test_summarize_performance_drawdown_uses_the_equity_path():
    result = performance_frame(
        trade_signal=[1, 0, -1, 1, 0, -1],
        realized_pnl=[0.0, 0.0, 200.0, 0.0, 0.0, -50.0],
    )
    metrics = summarize_performance(result)

    # Running peak is [10000, 10500, 10500, 11000, 11000, 11500]. The worst
    # ratio is 10200 / 10500 - 1 = -0.02857..., beating 10800 / 11000 - 1.
    assert metrics["max_drawdown"] == pytest.approx(10_200 / 10_500 - 1)


def test_summarize_performance_counts_round_trips_not_fills():
    # Two buys and two sells is two round trips, not four trades.
    result = performance_frame(
        trade_signal=[1, 0, -1, 1, 0, -1],
        realized_pnl=[0.0, 0.0, 200.0, 0.0, 0.0, -50.0],
    )
    metrics = summarize_performance(result)

    assert metrics["trade_count"] == 2
    # One of the two exits was profitable.
    assert metrics["win_rate"] == pytest.approx(0.5)


def test_summarize_performance_excludes_a_position_still_open_at_the_end():
    # Buy, sell at a profit, then buy again and never close. The open position
    # has no realized PnL, so it must not count as a trade or dilute win rate,
    # even though its value is still inside ending_equity.
    result = performance_frame(
        trade_signal=[1, 0, -1, 1, 0, 0],
        realized_pnl=[0.0, 0.0, 200.0, 0.0, 0.0, 0.0],
    )
    metrics = summarize_performance(result)

    assert metrics["trade_count"] == 1
    assert metrics["win_rate"] == pytest.approx(1.0)
    assert metrics["ending_equity"] == pytest.approx(11_500.0)


def test_summarize_performance_handles_a_run_with_no_trades():
    # Dividing by zero exits would crash. A strategy that never traded has a
    # win rate of 0.0 by definition.
    result = performance_frame(
        trade_signal=[0, 0, 0, 0, 0, 0],
        realized_pnl=[0.0] * 6,
    )
    metrics = summarize_performance(result)

    assert metrics["trade_count"] == 0
    assert metrics["win_rate"] == 0.0


def test_summarize_performance_rejects_an_empty_frame():
    with pytest.raises(ValueError, match="cannot be empty"):
        summarize_performance(pd.DataFrame())
