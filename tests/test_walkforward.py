"""Specification for alphanexus/walkforward.py.

These tests fail until walk-forward evaluation is implemented. They use the
synthetic benchmark fixtures (504 daily bars each), so they are offline and
deterministic.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from alphanexus.backtest import BacktestConfig, run_backtest
from alphanexus.strategies import StrategyConfig
from alphanexus.walkforward import Window, optimize, split_windows, walk_forward
from benchmarks.scenarios import load_fixture

GRID = [
    StrategyConfig(name="sma_crossover", fast_window=fast, slow_window=slow)
    for fast, slow in [(5, 20), (10, 20), (5, 40), (10, 40)]
]
COSTS = BacktestConfig(fee_bps=5, slippage_bps=5)
TRAIN, TEST = 200, 100


def prices() -> pd.DataFrame:
    return load_fixture("cyclical")


def sharpe(frame: pd.DataFrame, config: StrategyConfig) -> float:
    return run_backtest(frame, config, COSTS)[1]["sharpe_ratio"]


# --------------------------------------------------------------------------
# split_windows
# --------------------------------------------------------------------------


def test_windows_roll_forward_by_the_test_size():
    assert split_windows(100, 50, 20) == [Window(0, 50, 50, 70), Window(20, 70, 70, 90)]


def test_each_test_slice_starts_where_its_train_slice_ends():
    for window in split_windows(504, TRAIN, TEST):
        assert window.test_start == window.train_end
        assert window.train_end - window.train_start == TRAIN
        assert window.test_end - window.test_start == TEST


def test_test_slices_are_consecutive_and_never_overlap():
    windows = split_windows(504, TRAIN, TEST)
    for earlier, later in zip(windows, windows[1:], strict=False):
        assert later.test_start == earlier.test_end


def test_a_window_that_would_run_past_the_data_is_dropped():
    windows = split_windows(504, TRAIN, TEST)
    assert len(windows) == 3
    assert windows[-1].test_end <= 504


@pytest.mark.parametrize("train, test", [(0, 20), (50, 0), (-5, 20)])
def test_non_positive_sizes_are_refused(train, test):
    with pytest.raises(ValueError):
        split_windows(100, train, test)


def test_data_too_short_for_one_window_is_refused():
    with pytest.raises(ValueError):
        split_windows(60, 50, 20)


# --------------------------------------------------------------------------
# optimize
# --------------------------------------------------------------------------


def test_optimize_picks_the_highest_sharpe_config():
    data = prices()
    expected = max(GRID, key=lambda config: sharpe(data, config))

    config, best = optimize(data, GRID, COSTS)

    assert config == expected
    assert best == pytest.approx(sharpe(data, expected))


def test_ties_go_to_the_earliest_grid_entry():
    # A perfectly flat price never triggers a crossover, so every config
    # scores the same Sharpe (0) and the first one must win.
    flat = pd.DataFrame(
        {"date": [datetime(2024, 1, 1) + timedelta(days=i) for i in range(120)], "close": [100.0] * 120}
    )
    config, best = optimize(flat, GRID, COSTS)
    assert config == GRID[0]
    assert best == 0


def test_configs_that_cannot_warm_up_are_skipped():
    # 30 bars: enough for slow=20 (needs 21) but not slow=40 (needs 41).
    config, _ = optimize(prices().iloc[:30].reset_index(drop=True), GRID, COSTS)
    assert config.slow_window == 20


def test_optimize_refuses_when_no_config_can_run():
    with pytest.raises(ValueError):
        optimize(prices().iloc[:15].reset_index(drop=True), GRID, COSTS)


# --------------------------------------------------------------------------
# walk_forward
# --------------------------------------------------------------------------


def test_there_is_one_result_per_window():
    result = walk_forward(prices(), GRID, TRAIN, TEST, COSTS)
    assert [w.window for w in result.windows] == split_windows(504, TRAIN, TEST)


def test_each_choice_is_the_optimum_of_its_train_slice():
    data = prices()
    result = walk_forward(data, GRID, TRAIN, TEST, COSTS)

    for window_result in result.windows:
        w = window_result.window
        train = data.iloc[w.train_start : w.train_end].reset_index(drop=True)
        config, best = optimize(train, GRID, COSTS)
        assert window_result.config == config
        assert window_result.train_sharpe == pytest.approx(best)


def test_choices_never_see_data_after_their_train_slice():
    # The look-ahead test for walk-forward: wreck every price after a window's
    # train slice ends, and that window must still choose the same config.
    data = prices()
    baseline = walk_forward(data, GRID, TRAIN, TEST, COSTS)

    for index, window in enumerate(split_windows(len(data), TRAIN, TEST)):
        corrupted = data.copy()
        corrupted.loc[window.train_end :, ["open", "high", "low", "close"]] *= 3
        rerun = walk_forward(corrupted, GRID, TRAIN, TEST, COSTS)
        assert rerun.windows[index].config == baseline.windows[index].config


def test_trades_counted_for_a_window_fall_inside_its_test_slice():
    data = prices()
    result = walk_forward(data, GRID, TRAIN, TEST, COSTS)

    for window_result in result.windows:
        w = window_result.window
        test_dates = set(data["date"].iloc[w.test_start : w.test_end])
        assert all(date in test_dates for date in window_result.trade_dates)


def test_rsi_warmup_cannot_trade_before_test_window():
    data = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=40), "close": [100.0] * 40})
    config = StrategyConfig(name="rsi_mean_reversion", rsi_window=5, oversold=60, overbought=70)
    (result,) = walk_forward(data, [config], 20, 20, BacktestConfig(fee_bps=0, slippage_bps=0)).windows
    assert result.trade_dates == [data["date"].iloc[20]]
    assert result.test_return == pytest.approx(0)


def test_walk_forward_rejects_out_of_order_prices():
    with pytest.raises(ValueError, match="ordered by date"):
        walk_forward(prices().iloc[::-1], GRID, TRAIN, TEST, COSTS)


def test_summary_statistics_match_the_windows():
    result = walk_forward(prices(), GRID, TRAIN, TEST, COSTS)
    train = [w.train_sharpe for w in result.windows]
    test = [w.test_sharpe for w in result.windows]

    assert result.mean_train_sharpe == pytest.approx(sum(train) / len(train))
    assert result.mean_test_sharpe == pytest.approx(sum(test) / len(test))
    assert result.sharpe_degradation == pytest.approx(result.mean_train_sharpe - result.mean_test_sharpe)
