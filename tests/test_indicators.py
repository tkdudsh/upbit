import pandas as pd
import pytest
from strategy_engine import indicators


def test_sma():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = indicators.sma(s, period=3)
    assert result.isna().iloc[:2].all()
    assert result.iloc[2:].tolist() == pytest.approx([2.0, 3.0, 4.0])


def test_rsi():
    s = pd.Series([100, 102, 101, 104, 103, 106], dtype=float)
    result = indicators.rsi(s, period=3)
    assert result.iloc[3] == pytest.approx(83.333, abs=0.01)
    assert result.iloc[4] == pytest.approx(60.0, abs=0.01)
    assert result.iloc[5] == pytest.approx(85.714, abs=0.01)


def test_bollinger_band_width():
    s = pd.Series([1, 2, 3, 4, 5, 6], dtype=float)
    result = indicators.bollinger_band_width(s, period=3, num_std=2.0)
    assert result.iloc[2] == pytest.approx(2.0, abs=0.001)
    assert result.iloc[3] == pytest.approx(1.3333, abs=0.001)
    assert result.iloc[4] == pytest.approx(1.0, abs=0.001)
    assert result.iloc[5] == pytest.approx(0.8, abs=0.001)


def test_volume_ratio():
    v = pd.Series([10, 10, 10, 10, 20, 20], dtype=float)
    result = indicators.volume_ratio(v, short_period=2, long_period=4)
    assert result.iloc[:3].isna().all()
    assert result.iloc[5] == pytest.approx(20 / 15, abs=0.001)


def test_rolling_high_and_low():
    s = pd.Series([3, 1, 4, 1, 5, 9, 2, 6], dtype=float)
    high = indicators.rolling_high(s, period=3)
    low = indicators.rolling_low(s, period=3)
    assert high.tolist() == [3, 3, 4, 4, 5, 9, 9, 9]
    assert low.tolist() == [3, 1, 1, 1, 1, 1, 2, 2]


def test_pct_change_n():
    s = pd.Series([100, 110, 121], dtype=float)
    result = indicators.pct_change_n(s, n=2)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(0.21, abs=0.001)


def test_ma_slope():
    s = pd.Series([10, 12, 14, 16, 18, 20], dtype=float)
    result = indicators.ma_slope(s, period=2, lookback=2)
    assert result.iloc[3] == pytest.approx((15 - 11) / 11, abs=0.001)
    assert result.iloc[4] == pytest.approx((17 - 13) / 13, abs=0.001)
    assert result.iloc[5] == pytest.approx((19 - 15) / 15, abs=0.001)
