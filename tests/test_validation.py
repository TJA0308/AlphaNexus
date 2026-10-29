import pandas as pd
import pytest

from alphanexus.backtest import run_backtest
from alphanexus.strategies import StrategyConfig
from alphanexus.validation import validate_prices


def frame():
    return pd.DataFrame({"date": pd.date_range("2024-01-01", periods=8), "close": [10.] * 8})


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), "bad"])
def test_invalid_closes_never_reach_indicator_calculation(value):
    prices = frame().astype({"close": object})
    prices.loc[3, "close"] = value
    with pytest.raises(ValueError, match="close"):
        run_backtest(prices, StrategyConfig("sma_crossover", fast_window=2, slow_window=3))


@pytest.mark.parametrize("value", [pd.NaT, pd.Timestamp("2024-01-01"), "invalid"])
def test_missing_duplicate_or_invalid_dates_are_rejected(value):
    prices = frame().astype({"date": object})
    prices.loc[3, "date"] = value
    with pytest.raises(ValueError, match="dates"):
        validate_prices(prices)


def test_ohlc_consistency_and_volume_are_checked():
    prices = frame().assign(open=10., low=9., high=11., volume=0.)
    assert len(validate_prices(prices)) == 8
    for column, value, message in [("high", 9., "OHLC"), ("low", 11., "OHLC"), ("volume", -1., "volume")]:
        invalid = prices.copy()
        invalid.loc[0, column] = value
        with pytest.raises(ValueError, match=message):
            validate_prices(invalid)


def test_validation_sorts_without_mutation_and_preserves_timezone():
    prices = frame()
    prices["date"] = prices.date.dt.tz_localize("America/New_York")
    prices = prices.iloc[::-1]
    original = prices.copy()
    result = validate_prices(prices)
    assert result.date.is_monotonic_increasing
    assert str(result.date.dt.tz) == "America/New_York"
    pd.testing.assert_frame_equal(prices, original)


@pytest.mark.parametrize("config", [
    StrategyConfig("sma_crossover", fast_window=2.5),
    StrategyConfig("sma_crossover", slow_window=10001),
    StrategyConfig("rsi_mean_reversion", oversold=float("nan")),
    StrategyConfig("rsi_mean_reversion", oversold=80, overbought=20),
    StrategyConfig("bollinger_breakout", band_std=float("inf")),
])
def test_direct_strategy_callers_have_domain_validation(config):
    with pytest.raises(ValueError):
        config.validate()
