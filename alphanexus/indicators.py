from __future__ import annotations

import pandas as pd


def simple_moving_average(series: pd.Series, window: int) -> pd.Series:
    if window <= 0:
        raise ValueError("window must be greater than 0")
    return series.rolling(window=window, min_periods=window).mean()


def bollinger_bands(
    close: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    if window <= 1:
        raise ValueError("window must be greater than 1")
    if num_std <= 0:
        raise ValueError("num_std must be greater than 0")

    center = simple_moving_average(close, window)
    rolling_std = close.rolling(window=window, min_periods=window).std()

    return pd.DataFrame(
        {
            "center_line": center,
            "upper_band": center + (rolling_std * num_std),
            "lower_band": center - (rolling_std * num_std),
        }
    )


def relative_strength_index(close: pd.Series, window: int = 14) -> pd.Series:
    if window <= 1:
        raise ValueError("window must be greater than 1")

    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    # A zero average loss means uninterrupted gains and therefore RSI 100.
    # When both averages are zero, the market is flat and RSI is neutral.
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)
    rsi = rsi.mask((avg_loss == 0) & (avg_gain == 0), 50)
    return rsi.fillna(50)
