from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from alphanexus.indicators import bollinger_bands, relative_strength_index, simple_moving_average
from alphanexus.validation import MAX_WINDOW, finite_number, validate_prices

StrategyName = Literal["sma_crossover", "rsi_mean_reversion", "bollinger_breakout"]


@dataclass(frozen=True)
class StrategyConfig:
    name: StrategyName
    fast_window: int = 20
    slow_window: int = 50
    rsi_window: int = 14
    oversold: float = 30
    overbought: float = 70
    band_window: int = 20
    band_std: float = 2.0

    def validate(self) -> None:
        windows = {
            "sma_crossover": ("fast_window", "slow_window"),
            "rsi_mean_reversion": ("rsi_window",),
            "bollinger_breakout": ("band_window",),
        }
        if self.name not in windows:
            raise ValueError(f"unsupported strategy: {self.name}")
        for name in windows[self.name]:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 2 <= value <= MAX_WINDOW:
                raise ValueError(f"{name} must be an integer between 2 and {MAX_WINDOW}")
        if self.name == "sma_crossover" and self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be less than slow_window")
        if self.name == "rsi_mean_reversion":
            for name in ("oversold", "overbought"):
                finite_number(name, getattr(self, name), minimum=0, maximum=100, inclusive=False)
            if not self.oversold < self.overbought < 100:
                raise ValueError("oversold must be below overbought, and overbought below 100")
        if self.name == "bollinger_breakout":
            finite_number("band_std", self.band_std, minimum=0, maximum=100, inclusive=False)


def warmup_bars(config: StrategyConfig) -> int:
    """How many bars a strategy consumes before it can hold its first position.

    Every indicator here needs a full window of closes before it produces a
    value at all, and the one-bar signal lag costs one more on top of that.
    Below this many bars the strategy is not flat, it is undefined: the
    indicators are still NaN and no position is reachable.
    """
    if config.name == "sma_crossover":
        indicator_bars = config.slow_window
    elif config.name == "rsi_mean_reversion":
        # RSI is built on close.diff(), which spends the first bar.
        indicator_bars = config.rsi_window + 1
    elif config.name == "bollinger_breakout":
        indicator_bars = config.band_window
    else:
        raise ValueError(f"unsupported strategy: {config.name}")

    return indicator_bars + 1


def generate_signals(prices: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    config.validate()
    df = validate_prices(prices)
    df["signal"] = 0

    if config.name == "sma_crossover":
        df["fast_sma"] = simple_moving_average(df["close"], config.fast_window)
        df["slow_sma"] = simple_moving_average(df["close"], config.slow_window)
        df["signal"] = np.where(df["fast_sma"] > df["slow_sma"], 1, 0)

    elif config.name == "rsi_mean_reversion":
        df["rsi"] = relative_strength_index(df["close"], config.rsi_window)
        df["signal"] = np.select(
            [df["rsi"] < config.oversold, df["rsi"] > config.overbought],
            [1, 0],
            default=np.nan,
        )
        df["signal"] = df["signal"].ffill().fillna(0).astype(int)

    elif config.name == "bollinger_breakout":
        bands = bollinger_bands(df["close"], config.band_window, config.band_std)
        df = pd.concat([df, bands], axis=1)
        df["signal"] = np.select(
            [df["close"] > df["upper_band"], df["close"] < df["center_line"]],
            [1, 0],
            default=np.nan,
        )
        df["signal"] = df["signal"].ffill().fillna(0).astype(int)

    else:
        raise ValueError(f"unsupported strategy: {config.name}")

    # Lag the target position by one bar before turning it into trades.
    # `signal` for bar t is derived from bar t's close, but we cannot both
    # observe that close and trade on it. Shifting by one bar means a signal
    # seen at bar t is acted on at bar t+1, which removes the look-ahead bias.
    df["signal"] = df["signal"].shift(1).fillna(0).astype(int)

    df["trade_signal"] = df["signal"].diff().fillna(df["signal"]).astype(int)
    return df

