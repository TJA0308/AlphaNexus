import pandas as pd
import pytest

from alphanexus.indicators import bollinger_bands, relative_strength_index, simple_moving_average


def test_simple_moving_average_uses_full_window():
    series = pd.Series([10, 20, 30, 40])

    result = simple_moving_average(series, 3)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == 20
    assert result.iloc[3] == 30


def test_bollinger_bands_rejects_invalid_standard_deviation():
    with pytest.raises(ValueError):
        bollinger_bands(pd.Series([1, 2, 3]), window=2, num_std=0)


def test_rsi_stays_between_zero_and_one_hundred():
    close = pd.Series([10, 11, 12, 11, 13, 14, 13, 15, 16, 14, 15, 17, 18, 19, 20, 18])

    result = relative_strength_index(close, window=5)

    assert result.between(0, 100).all()

