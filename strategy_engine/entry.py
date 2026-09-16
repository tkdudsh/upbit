import pandas as pd
from . import config, indicators


def is_recent_pump(df: pd.DataFrame) -> bool:
    ret = indicators.pct_change_n(df["close"], config.RECENT_PUMP_LOOKBACK_DAYS)
    return bool(ret.iloc[-1] >= config.RECENT_PUMP_RETURN_THRESHOLD)


def is_near_high(df: pd.DataFrame) -> bool:
    high = indicators.rolling_high(df["close"], config.HIGH_LOOKBACK_DAYS)
    close = df["close"].iloc[-1]
    distance = (high.iloc[-1] - close) / high.iloc[-1]
    return bool(distance <= config.NEAR_HIGH_THRESHOLD)


def is_deep_pullback(df: pd.DataFrame) -> bool:
    high = indicators.rolling_high(df["close"], config.HIGH_LOOKBACK_DAYS)
    close = df["close"].iloc[-1]
    distance = (high.iloc[-1] - close) / high.iloc[-1]
    return bool(distance >= config.DEEP_PULLBACK_THRESHOLD)


def is_near_ma_support(df: pd.DataFrame) -> bool:
    close = df["close"]
    last_close = close.iloc[-1]
    for period in config.MA_SUPPORT_PERIODS:
        ma = indicators.sma(close, period)
        if pd.isna(ma.iloc[-1]):
            continue
        if abs(last_close - ma.iloc[-1]) / ma.iloc[-1] <= config.MA_SUPPORT_BAND:
            return True
    return False


def is_oversold_bounce(df: pd.DataFrame) -> bool:
    rsi = indicators.rsi(df["close"], config.RSI_PERIOD)
    if pd.isna(rsi.iloc[-1]) or pd.isna(rsi.iloc[-2]):
        return False
    return bool(rsi.iloc[-1] <= config.RSI_OVERSOLD and rsi.iloc[-1] > rsi.iloc[-2])


def is_volume_recovering(df: pd.DataFrame) -> bool:
    ratio = indicators.volume_ratio(
        df["volume"], config.VOLUME_RECOVERY_SHORT_PERIOD, config.VOLUME_RECOVERY_LONG_PERIOD
    )
    if pd.isna(ratio.iloc[-1]):
        return False
    return bool(ratio.iloc[-1] >= config.VOLUME_RECOVERY_RATIO)


def is_volatility_squeeze_expanding(df: pd.DataFrame) -> bool:
    width = indicators.bollinger_band_width(df["close"], config.BB_PERIOD, config.BB_STD)
    recent_min = width.rolling(window=config.BB_SQUEEZE_LOOKBACK_DAYS, min_periods=config.BB_PERIOD).min()
    if len(width) < 2 or pd.isna(width.iloc[-2]) or pd.isna(recent_min.iloc[-2]):
        return False
    was_squeezed = width.iloc[-2] <= recent_min.iloc[-2] * (1 + config.BB_SQUEEZE_TOLERANCE)
    now_expanding = width.iloc[-1] > width.iloc[-2]
    return bool(was_squeezed and now_expanding)


def entry_allowed(df: pd.DataFrame) -> bool:
    excluded = is_recent_pump(df) or is_near_high(df)
    if excluded:
        return False
    confirmed = any([
        is_deep_pullback(df),
        is_near_ma_support(df),
        is_oversold_bounce(df),
        is_volume_recovering(df),
        is_volatility_squeeze_expanding(df),
    ])
    return confirmed
