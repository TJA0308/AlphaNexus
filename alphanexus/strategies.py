from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from alphanexus.indicators import bollinger_bands, relative_strength_index, simple_moving_average


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
    required_columns = {"date", "close"}
    missing = required_columns.difference(prices.columns)
    if missing:
        raise ValueError(f"prices is missing required columns: {sorted(missing)}")

    df = prices.copy().sort_values("date").reset_index(drop=True)
    df["signal"] = 0

    if config.name == "sma_crossover":
        if config.fast_window >= config.slow_window:
            raise ValueError("fast_window must be less than slow_window")
        df["fast_sma"] = simple_moving_average(df["close"], config.fast_window)
        df["slow_sma"] = simple_moving_average(df["close"], config.slow_window)
        df["signal"] = np.where(df["fast_sma"] > df["slow_sma"], 1, 0)

    elif config.name == "rsi_mean_reversion":
        if config.oversold >= config.overbought:
            raise ValueError("oversold must be below overbought")
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

