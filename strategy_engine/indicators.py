import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def bollinger_band_width(series: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.Series:
    mid = series.rolling(window=period, min_periods=period).mean()
    std = series.rolling(window=period, min_periods=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return (upper - lower) / mid


def volume_ratio(volume: pd.Series, short_period: int = 5, long_period: int = 20) -> pd.Series:
    short_ma = volume.rolling(window=short_period, min_periods=short_period).mean()
    long_ma = volume.rolling(window=long_period, min_periods=long_period).mean()
    return short_ma / long_ma


def rolling_high(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).max()


def rolling_low(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).min()


def pct_change_n(series: pd.Series, n: int) -> pd.Series:
    return series.pct_change(periods=n)


def ma_slope(series: pd.Series, period: int, lookback: int) -> pd.Series:
    ma = sma(series, period)
    return (ma - ma.shift(lookback)) / ma.shift(lookback)
