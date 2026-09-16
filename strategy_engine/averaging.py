import pandas as pd
from . import config, indicators, regime


def has_reached_step(
    reference_price: float,
    current_price: float,
    rounds_used: int,
    step_pct: float = config.AVERAGING_STEP_PCT,
) -> bool:
    # `reference_price` is the stable baseline the -10/-20/-30% ladder is
    # measured from — engine.py passes Position.entry_price (the ORIGINAL
    # entry, never recomputed), not the running weighted average. Passing a
    # value that itself drops after each round (like avg_price) makes the
    # ladder overshoot its documented envelope, since each round would then
    # be chasing an already-lower target. See the Task 8 fix-wave history.
    if rounds_used >= config.MAX_AVERAGING_ROUNDS:
        return False
    required_drop = step_pct * (rounds_used + 1)
    actual_drop = (reference_price - current_price) / reference_price
    return actual_drop >= required_drop


def is_support_alive(df: pd.DataFrame, band: float = config.SUPPORT_SURVIVAL_BAND) -> bool:
    # Use the rolling low as of the prior bar (excluding today's close), since
    # indicators.rolling_low's window is inclusive of the current row — using
    # low.iloc[-1] would always include current_price itself, making a newly
    # set low trivially "within band" of itself. Mirrors the is_capitulation
    # pattern below, which likewise looks at avg_volume.iloc[-2].
    low = indicators.rolling_low(df["close"], config.SUPPORT_LOOKBACK_DAYS)
    current = df["close"].iloc[-1]
    return bool(current >= low.iloc[-2] * (1 - band))


def is_capitulation(df: pd.DataFrame) -> bool:
    close = df["close"]
    volume = df["volume"]
    is_down_day = close.iloc[-1] < close.iloc[-2]
    avg_volume = volume.rolling(
        window=config.CAPITULATION_VOLUME_LOOKBACK_DAYS, min_periods=config.CAPITULATION_VOLUME_LOOKBACK_DAYS
    ).mean()
    if pd.isna(avg_volume.iloc[-2]):
        return False
    volume_spike = volume.iloc[-1] >= avg_volume.iloc[-2] * config.CAPITULATION_VOLUME_MULTIPLIER
    return bool(is_down_day and volume_spike)


def averaging_allowed(
    coin_df: pd.DataFrame,
    btc_df: pd.DataFrame,
    reference_price: float,
    current_price: float,
    rounds_used: int,
) -> bool:
    if not has_reached_step(reference_price, current_price, rounds_used):
        return False
    if not is_support_alive(coin_df):
        return False
    if is_capitulation(coin_df):
        return False
    if regime.is_bear_market(btc_df, coin_df):
        return False
    return True
