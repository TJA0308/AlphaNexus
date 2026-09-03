from datetime import datetime, timedelta

import pandas as pd
import pytest

from alphanexus.backtest import BacktestConfig, run_backtest
from alphanexus.strategies import StrategyConfig, warmup_bars


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


def price_frame(close: list[float]) -> pd.DataFrame:
    start = datetime(2024, 1, 1)
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


def rising_prices() -> pd.DataFrame:
    """A path that is still trending up on the final bar.

    The strategy is therefore holding a position when the data runs out, which
    is the case that separates marking to market from realizing a trade.
    """
    return price_frame([10, 10, 10, 10, 10, 11, 12, 13, 14, 15, 16, 17, 18])


def two_round_trips() -> pd.DataFrame:
    """Up, down, up, down: enough to enter and exit twice, ending net down."""
    return price_frame(
        [10] * 5
        + [11, 12, 13, 14, 15]
        + [14, 13, 12, 11, 10]
        + [11, 12, 13, 14, 15]
        + [14, 13, 12, 11, 10]
    )


def two_winning_round_trips() -> pd.DataFrame:
    """Two round trips that each close well above their entry.

    The rallies are long enough that the exit (which lags the top by a couple
    of bars) still lands above the entry, so the account grows between trades.
    """
    return price_frame(
        [10] * 5
        + [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        + [19, 18, 17, 16]
        + [17, 18, 19, 20, 21, 22]
        + [21, 20, 19, 18, 17]
    )


CROSSOVER = StrategyConfig(name="sma_crossover", fast_window=2, slow_window=5)


def final_equity(prices: pd.DataFrame, **config) -> float:
    result, _ = run_backtest(prices, CROSSOVER, BacktestConfig(**config))
    return float(result["portfolio_value"].iloc[-1])


# --------------------------------------------------------------------------
# Trading costs
# --------------------------------------------------------------------------


def test_fees_and_slippage_both_cost_money():
    # Guards the sign of fee_rate and slippage_rate. If either were applied in
    # the wrong direction, trading would become free or profitable and every
    # other test in this file would still pass.
    prices = two_round_trips()
    free = final_equity(prices, fee_bps=0, slippage_bps=0)

    assert final_equity(prices, fee_bps=10, slippage_bps=0) < free
    assert final_equity(prices, fee_bps=0, slippage_bps=10) < free
    assert final_equity(prices, fee_bps=10, slippage_bps=10) < free


def test_higher_costs_hurt_more():
    prices = two_round_trips()

    cheap = final_equity(prices, fee_bps=5, slippage_bps=5)
    expensive = final_equity(prices, fee_bps=50, slippage_bps=50)

    assert expensive < cheap


def test_slippage_fills_a_buy_above_the_close():
    # Paying up on entry buys strictly fewer shares for the same cash.
    prices = two_round_trips()

    clean, _ = run_backtest(prices, CROSSOVER, BacktestConfig(fee_bps=0, slippage_bps=0))
    slipped, _ = run_backtest(prices, CROSSOVER, BacktestConfig(fee_bps=0, slippage_bps=100))

    first_clean_buy = clean[clean["trade_signal"] == 1].iloc[0]
    first_slipped_buy = slipped[slipped["trade_signal"] == 1].iloc[0]

    assert first_slipped_buy["trade_shares"] < first_clean_buy["trade_shares"]


def test_a_costless_backtest_leaves_no_cash_stranded():
    # With allocation 1 and no fees the entry should deploy the whole balance,
    # not 99.99% of it. A rounding slip here silently shrinks every position.
    result, _ = run_backtest(
        two_round_trips(),
        CROSSOVER,
        BacktestConfig(starting_cash=10_000, fee_bps=0, slippage_bps=0),
    )

    first_buy_index = result.index[result["trade_signal"] == 1][0]

    assert result.loc[first_buy_index, "cash"] == pytest.approx(0.0)


# --------------------------------------------------------------------------
# Allocation
# --------------------------------------------------------------------------


def test_allocation_caps_how_much_cash_is_deployed():
    result, _ = run_backtest(
        two_round_trips(),
        CROSSOVER,
        BacktestConfig(starting_cash=10_000, fee_bps=0, slippage_bps=0, allocation=0.5),
    )

    first_buy_index = result.index[result["trade_signal"] == 1][0]

    # Half in, half held back as cash.
    assert result.loc[first_buy_index, "cash"] == pytest.approx(5_000.0)


def test_a_smaller_allocation_dampens_the_outcome():
    # This path ends below where it started, so less exposure means a smaller
    # loss. The point is that allocation actually scales risk.
    prices = two_round_trips()

    full = final_equity(prices, starting_cash=10_000, fee_bps=0, slippage_bps=0, allocation=1.0)
    tenth = final_equity(prices, starting_cash=10_000, fee_bps=0, slippage_bps=0, allocation=0.1)

    assert full < 10_000
    assert full < tenth < 10_000


def test_allocation_is_a_fraction_of_current_cash_not_of_starting_cash():
    # Pinning a real modelling decision. Sizing off the *current* balance means
    # exposure compounds: a winning round trip makes the next entry larger.
    # Sizing off starting_cash would instead make every entry identical no
    # matter how the account had performed.
    result, _ = run_backtest(
        two_winning_round_trips(),
        CROSSOVER,
        BacktestConfig(starting_cash=10_000, fee_bps=0, slippage_bps=0, allocation=0.5),
    )

    buys = result.index[result["trade_signal"] == 1]
    assert len(buys) == 2

    for buy in buys:
        cash_before = result.loc[buy - 1, "cash"]
        # Half of whatever was on hand at that moment went into the position.
        assert result.loc[buy, "cash"] == pytest.approx(cash_before * 0.5)

    # And because the first trip won, the second entry was the bigger one.
    assert result.loc[buys[1], "cash"] > result.loc[buys[0], "cash"]


# --------------------------------------------------------------------------
# Config validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize("starting_cash", [0, -1, -10_000])
def test_non_positive_starting_cash_is_rejected(starting_cash):
    with pytest.raises(ValueError, match="starting_cash"):
        run_backtest(sample_prices(), CROSSOVER, BacktestConfig(starting_cash=starting_cash))


@pytest.mark.parametrize("allocation", [0, -0.5, 1.01, 2])
def test_allocation_outside_its_bounds_is_rejected(allocation):
    with pytest.raises(ValueError, match="allocation"):
        run_backtest(sample_prices(), CROSSOVER, BacktestConfig(allocation=allocation))


def test_allocation_of_exactly_one_is_allowed():
    # The upper bound is inclusive: going all in is a legitimate config.
    result, _ = run_backtest(sample_prices(), CROSSOVER, BacktestConfig(allocation=1.0))

    assert not result.empty


def test_too_little_data_is_rejected_rather_than_reported_as_flat():
    # Regression test. This used to succeed and report a confident 0.00%
    # return: with fewer bars than the slow window the SMAs are all NaN, the
    # signal is 0 everywhere, and the result was indistinguishable from a
    # strategy that had genuinely been tested and chose not to trade.
    with pytest.raises(ValueError, match="not enough data"):
        run_backtest(
            price_frame([10, 11]),
            StrategyConfig(name="sma_crossover", fast_window=2, slow_window=5),
            BacktestConfig(),
        )


def test_the_warmup_requirement_is_reported_in_the_error():
    # The caller needs to know how much more history to ask for, not just that
    # something was wrong.
    with pytest.raises(ValueError, match="3 bars available, 6 needed"):
        run_backtest(
            price_frame([10, 11, 12]),
            StrategyConfig(name="sma_crossover", fast_window=2, slow_window=5),
            BacktestConfig(),
        )


def test_exactly_enough_data_is_accepted():
    # The boundary is inclusive: slow_window bars to warm the SMA up, plus one
    # for the signal lag. One bar fewer must fail, this many must pass.
    config = StrategyConfig(name="sma_crossover", fast_window=2, slow_window=5)

    result, _ = run_backtest(price_frame([10, 11, 12, 13, 14, 15]), config, BacktestConfig())
    assert len(result) == 6

    with pytest.raises(ValueError, match="not enough data"):
        run_backtest(price_frame([10, 11, 12, 13, 14]), config, BacktestConfig())


@pytest.mark.parametrize(
    "config, required",
    [
        (StrategyConfig(name="sma_crossover", fast_window=2, slow_window=20), 21),
        # RSI is built on close.diff(), so it spends one extra bar.
        (StrategyConfig(name="rsi_mean_reversion", rsi_window=14), 16),
        (StrategyConfig(name="bollinger_breakout", band_window=20), 21),
    ],
)
def test_every_strategy_declares_its_own_warmup(config, required):
    assert warmup_bars(config) == required

    with pytest.raises(ValueError, match="not enough data"):
        run_backtest(price_frame([10.0] * (required - 1)), config, BacktestConfig())


def test_an_empty_frame_is_rejected():
    with pytest.raises(ValueError, match="not enough data"):
        run_backtest(price_frame([]), CROSSOVER, BacktestConfig())


# --------------------------------------------------------------------------
# Open positions and the benchmark
# --------------------------------------------------------------------------


def test_a_position_still_open_at_the_end_is_marked_to_market():
    result, metrics = run_backtest(
        rising_prices(),
        CROSSOVER,
        BacktestConfig(starting_cash=10_000, fee_bps=0, slippage_bps=0),
    )

    last = result.iloc[-1]
    assert last["shares"] > 0, "expected the strategy to still be long"

    # Equity reflects the unrealized position...
    assert last["portfolio_value"] == pytest.approx(last["cash"] + last["shares"] * last["close"])
    assert last["portfolio_value"] > 10_000

    # ...but nothing has been realized, so it is not a completed trade.
    assert metrics["trade_count"] == 0


def test_the_benchmark_starts_from_the_same_cash_as_the_strategy():
    # total_return and benchmark_return are only comparable if both curves
    # begin at the same number.
    result, _ = run_backtest(two_round_trips(), CROSSOVER, BacktestConfig(starting_cash=25_000))

    assert result["benchmark_value"].iloc[0] == pytest.approx(25_000)
    assert result["portfolio_value"].iloc[0] == pytest.approx(25_000)


def test_the_benchmark_tracks_buy_and_hold():
    result, metrics = run_backtest(two_round_trips(), CROSSOVER, BacktestConfig(starting_cash=10_000))

    closes = result["close"]
    expected = closes.iloc[-1] / closes.iloc[0] - 1

    assert metrics["benchmark_return"] == pytest.approx(expected)
