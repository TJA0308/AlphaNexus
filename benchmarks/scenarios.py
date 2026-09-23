from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from alphanexus.backtest import BacktestConfig
from alphanexus.strategies import StrategyConfig

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

FIXTURE_ASSETS = [
    "trend_up",
    "trend_down",
    "mean_revert",
    "volatile",
    "breakout",
    "cyclical",
    "flat_noise",
    "shock_recovery",
]

DATE_WINDOWS = {
    "full": ("2023-01-03", "2024-12-05"),
    "first_half": ("2023-01-03", "2023-12-29"),
    "second_half": ("2024-01-02", "2024-12-05"),
}

STRATEGIES = {
    "sma_crossover": StrategyConfig(name="sma_crossover", fast_window=10, slow_window=30),
    "rsi_mean_reversion": StrategyConfig(name="rsi_mean_reversion", rsi_window=14, oversold=35, overbought=65),
    "bollinger_breakout": StrategyConfig(name="bollinger_breakout", band_window=20, band_std=2.0),
}

DEFAULT_BACKTEST_CONFIG = BacktestConfig(
    starting_cash=10_000,
    fee_bps=5,
    slippage_bps=5,
    allocation=1,
    interval="1d",
)


@dataclass(frozen=True)
class BenchmarkScenario:
    asset: str
    date_window: str
    strategy_name: str
    strategy_config: StrategyConfig
    backtest_config: BacktestConfig = DEFAULT_BACKTEST_CONFIG

    @property
    def id(self) -> str:
        return f"{self.asset}:{self.date_window}:{self.strategy_name}"


def iter_scenarios() -> Iterable[BenchmarkScenario]:
    for asset in FIXTURE_ASSETS:
        for date_window in DATE_WINDOWS:
            for strategy_name, strategy_config in STRATEGIES.items():
                yield BenchmarkScenario(
                    asset=asset,
                    date_window=date_window,
                    strategy_name=strategy_name,
                    strategy_config=strategy_config,
                )


def load_fixture(asset: str) -> pd.DataFrame:
    path = FIXTURE_DIR / f"{asset}.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing benchmark fixture: {path}")

    return pd.read_csv(path)


def load_prices_for_scenario(scenario: BenchmarkScenario) -> pd.DataFrame:
    start, end = DATE_WINDOWS[scenario.date_window]
    prices = load_fixture(scenario.asset)
    window = prices[(prices["date"] >= start) & (prices["date"] <= end)].copy()
    if window.empty:
        raise ValueError(f"scenario {scenario.id} has no fixture rows")
    return window.reset_index(drop=True)
