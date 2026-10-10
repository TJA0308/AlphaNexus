"""Walk-forward evaluation: tune on one period, test on the next, roll forward.

A single backtest picks its parameters and measures them on the same data,
which flatters them. Walk-forward splits the history into consecutive
windows. In each one, parameters are chosen using only the TRAIN slice and
then run, unchanged, on the TEST slice that follows. Comparing train Sharpe
with test Sharpe shows how much of the in-sample result survives on data the
choice never saw.

    |---- train 0 ----|-- test 0 --|
               |---- train 1 ----|-- test 1 --|
                          |---- train 2 ----|-- test 2 --|

This module is a specification to implement. Every function below says what
it must do; tests/test_walkforward.py checks it. Reuse the existing engine:
`run_backtest` (alphanexus/backtest.py) and `warmup_bars`
(alphanexus/strategies.py). Do not change the engine itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import pandas as pd

from alphanexus.backtest import BacktestConfig
from alphanexus.strategies import StrategyConfig


class Window(NamedTuple):
    """Positional bar ranges, half-open like Python slices: [start, end)."""

    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass(frozen=True)
class WindowResult:
    window: Window
    config: StrategyConfig  # the grid entry chosen on the train slice
    train_sharpe: float  # Sharpe of `config` on the train slice
    test_sharpe: float  # Sharpe of the same `config` on the test slice
    test_return: float  # total return over the test slice
    trade_dates: list  # dates (from prices["date"]) of trades executed in the test slice


@dataclass(frozen=True)
class WalkForwardResult:
    windows: list[WindowResult]

    @property
    def mean_train_sharpe(self) -> float:
        raise NotImplementedError

    @property
    def mean_test_sharpe(self) -> float:
        raise NotImplementedError

    @property
    def sharpe_degradation(self) -> float:
        """Mean train Sharpe minus mean test Sharpe. Large and positive means overfit."""
        raise NotImplementedError


def split_windows(n_bars: int, train_bars: int, test_bars: int) -> list[Window]:
    """Rolling train/test windows over `n_bars` bars.

    - Each test slice starts where its train slice ends.
    - The next window starts `test_bars` later, so test slices are consecutive
      and never overlap.
    - A final window whose test slice would run past `n_bars` is dropped.
    - Raise ValueError if either size is not positive, or if not even one
      full window fits.
    """
    raise NotImplementedError


def optimize(
    prices: pd.DataFrame,
    grid: list[StrategyConfig],
    backtest_config: BacktestConfig | None = None,
) -> tuple[StrategyConfig, float]:
    """Return the grid entry with the highest Sharpe on `prices`, and that Sharpe.

    - Skip configs whose warm-up needs more bars than `prices` has
      (`warmup_bars(config) > len(prices)`); they cannot be evaluated.
    - Ties go to the earliest entry in `grid`, so results are deterministic.
    - Raise ValueError if no config can be evaluated.
    """
    raise NotImplementedError


def walk_forward(
    prices: pd.DataFrame,
    grid: list[StrategyConfig],
    train_bars: int,
    test_bars: int,
    backtest_config: BacktestConfig | None = None,
) -> WalkForwardResult:
    """Run `optimize` on each train slice and evaluate the winner on its test slice.

    - The choice for a window must depend only on that window's train slice.
      Changing prices inside a test slice must not change which config is chosen.
    - Trades counted for a window must fall inside its test slice. The
      indicators need history to warm up: decide how to give the test run
      enough context without letting it trade before `test_start` (hint:
      `warmup_bars`), and be ready to explain your choice.
    """
    raise NotImplementedError
