import pandas as pd
from . import config, indicators


def is_downtrend(
    df: pd.DataFrame,
    ma_period: int = config.REGIME_MA_PERIOD,
    slope_lookback: int = config.REGIME_SLOPE_LOOKBACK_DAYS,
) -> bool:
    close = df["close"]
    ma = indicators.sma(close, ma_period)
    slope = indicators.ma_slope(close, ma_period, slope_lookback)
    return bool(close.iloc[-1] < ma.iloc[-1] and slope.iloc[-1] < 0)


def is_bear_market(
    btc_df: pd.DataFrame,
    coin_df: pd.DataFrame,
    ma_period: int = config.REGIME_MA_PERIOD,
    slope_lookback: int = config.REGIME_SLOPE_LOOKBACK_DAYS,
) -> bool:
    return is_downtrend(btc_df, ma_period, slope_lookback) and is_downtrend(
        coin_df, ma_period, slope_lookback
    )
