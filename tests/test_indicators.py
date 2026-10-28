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

    assert result.iloc[:5].isna().all()
    assert result.iloc[5:].between(0, 100).all()


def test_rsi_handles_uninterrupted_gains_losses_and_flat_prices():
    rising = relative_strength_index(pd.Series(range(1, 31), dtype=float), window=14)
    falling = relative_strength_index(pd.Series(range(30, 0, -1), dtype=float), window=14)
    flat = relative_strength_index(pd.Series([10.0] * 30), window=14)

    assert rising.iloc[-1] == 100
    assert falling.iloc[-1] == 0
    assert flat.iloc[-1] == 50


def test_rsi_matches_hand_calculated_wilder_seed_and_recurrence():
    # Changes: +1, -1, +2, -1, +2. Seed gains=1, losses=1/3.
    # Next averages: gains=2/3, losses=5/9; then gains=10/9, losses=10/27.
    close = pd.Series([10, 11, 10, 12, 11, 13], index=list("abcdef"), dtype=float)
    original = close.copy()
    result = relative_strength_index(close, window=3)
    assert result.iloc[:3].isna().all()
    assert result.iloc[3:].tolist() == pytest.approx([75, 100 * 6 / 11, 75])
    pd.testing.assert_series_equal(close, original)
    assert result.index.equals(close.index)


def test_rsi_short_input_remains_undefined():
    assert relative_strength_index(pd.Series([10, 11, 10]), window=3).isna().all()
