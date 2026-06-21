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

    df["trade_signal"] = df["signal"].diff().fillna(df["signal"]).astype(int)
    return df

