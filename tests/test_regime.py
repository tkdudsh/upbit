import pandas as pd
from strategy_engine import regime


def _df_from_closes(closes):
    return pd.DataFrame({"close": closes})


def test_is_downtrend_true_for_declining_prices():
    closes = [50 - i for i in range(10)]  # steadily declining
    df = _df_from_closes(closes)
    assert regime.is_downtrend(df, ma_period=3, slope_lookback=2) is True


def test_is_downtrend_false_for_rising_prices():
    closes = [50 + i for i in range(10)]  # steadily rising
    df = _df_from_closes(closes)
    assert regime.is_downtrend(df, ma_period=3, slope_lookback=2) is False


def test_is_bear_market_requires_both_btc_and_coin_down():
    declining = _df_from_closes([50 - i for i in range(10)])
    rising = _df_from_closes([50 + i for i in range(10)])

    assert regime.is_bear_market(declining, declining, ma_period=3, slope_lookback=2) is True
    assert regime.is_bear_market(declining, rising, ma_period=3, slope_lookback=2) is False
    assert regime.is_bear_market(rising, declining, ma_period=3, slope_lookback=2) is False
    assert regime.is_bear_market(rising, rising, ma_period=3, slope_lookback=2) is False
