# Altcoin Strategy Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python signal-computation + backtest engine that turns the "농부 매매법" discretionary trading philosophy into quantitative, config-driven entry / take-profit / averaging-down / bear-market signals for Upbit KRW-market altcoins — no live order execution yet, no real-time AI calls.

**Architecture:** A `strategy_engine` package with pure-function indicator/signal modules (`indicators.py`, `regime.py`, `entry.py`, `exit_signal.py`, `averaging.py`), a `Portfolio`/`Position` state model (`portfolio.py`), a daily orchestration loop that applies a fixed decision priority (`engine.py`), and a `backtest/` sub-package that replays historical daily candles fetched from Upbit's public REST API through that loop and reports performance metrics. Historical/live candle fetching lives in `upbit_client.py`, isolated behind `requests` calls so it can be mocked in tests.

**Tech Stack:** Python 3.11+, pandas, requests, pytest (no live-trading libraries — this plan produces signals and backtest results only).

**Spec:** `prompt/strategy_topic.md` (quantitative mapping + open decisions), grounded in `prompt/simple_spec.md` (original discretionary philosophy).

## Global Constraints

- Universe: Upbit KRW-market altcoins (`KRW-*`, excluding `KRW-BTC`); `KRW-BTC` is fetched separately as the regime/BTC-trend reference.
- Indicator candle basis: daily (1d) — v1 hypothesis, to be compared against weekly via backtest later; do not hardcode "weekly" anywhere.
- Take-profit: +5% on average entry price, full sell. No partial/staged take-profit in v1 (explicitly out of scope).
- Averaging-down: triggered at -10% steps from average entry price, conditional (never automatic), max 3 rounds (4 total buys per coin, covers down to -30%).
- No mechanical stop-loss anywhere in this codebase.
- No live order placement in this plan — output is computed signals + backtest results only.
- No real-time AI/LLM calls anywhere in the signal path — every decision must be a deterministic function of historical OHLCV data and the config constants below.
- Decision priority per cycle, enforced in `engine.py`: (1) take-profit on held positions, (2) averaging-down on remaining held positions, (3) new entries — **only if no averaging-down was executed that cycle** across any held position.
- Concurrent coin holdings: unlimited. Total-capital constraints are out of scope for this backtest (assume sufficient capital for every signaled trade); this is a signal/backtest engine, not a live capital allocator.
- All thresholds live in `strategy_engine/config.py` as named constants — never inline magic numbers in logic modules.
- `prompt/strategy_topic.md` §3-1 splits a live system into a daily batch (structural signals) and a real-time/short-polling loop (take-profit/averaging triggers). Historical data only comes as daily candles, so this backtest engine necessarily evaluates every signal — including take-profit and averaging triggers — once per day against that day's close. This is a backtest approximation of the real-time loop, not the real-time loop itself; building actual intraday monitoring is live-execution scope, outside this plan.

---

## File Structure

```
strategy_engine/
    __init__.py
    config.py          # every tunable threshold, one place
    upbit_client.py     # Upbit public REST API: market list + daily candles
    indicators.py        # pure indicator functions on pandas Series
    regime.py            # per-asset downtrend detection + BTC/coin dual gate
    entry.py              # entry predicates + entry_allowed composition
    exit_signal.py         # take-profit check
    averaging.py            # averaging-down predicates + averaging_allowed composition
    portfolio.py             # Position / ClosedTrade / Portfolio state
    engine.py                 # run_daily_cycle: applies the decision-priority order
    backtest/
        __init__.py
        metrics.py             # compute_metrics from closed trades
        runner.py               # run_backtest: iterate historical dates through engine
    scripts/
        __init__.py
        run_backtest.py          # CLI: fetch real data, run backtest, print metrics
tests/
    test_upbit_client.py
    test_indicators.py
    test_regime.py
    test_entry.py
    test_exit_signal.py
    test_averaging.py
    test_portfolio.py
    test_engine.py
    test_backtest_metrics.py
    test_backtest_runner.py
requirements.txt
```

---

### Task 1: Project scaffolding + KRW market list client

**Files:**
- Create: `requirements.txt`
- Create: `strategy_engine/__init__.py`
- Create: `strategy_engine/upbit_client.py`
- Test: `tests/test_upbit_client.py`

**Interfaces:**
- Produces: `upbit_client.get_krw_markets() -> list[str]`

- [ ] **Step 1: Create `requirements.txt`**

```
pandas>=2.0
requests>=2.31
pytest>=8.0
```

- [ ] **Step 2: Write the failing test for `get_krw_markets`**

```python
# tests/test_upbit_client.py
from unittest.mock import patch, MagicMock
from strategy_engine import upbit_client


@patch("strategy_engine.upbit_client.requests.get")
def test_get_krw_markets_filters_and_excludes_btc(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {"market": "KRW-BTC", "korean_name": "비트코인"},
        {"market": "KRW-ETH", "korean_name": "이더리움"},
        {"market": "KRW-XRP", "korean_name": "리플"},
        {"market": "BTC-ETH", "korean_name": "이더리움"},
    ]
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    markets = upbit_client.get_krw_markets()

    assert markets == ["KRW-ETH", "KRW-XRP"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_upbit_client.py::test_get_krw_markets_filters_and_excludes_btc -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError` (module/function doesn't exist yet)

- [ ] **Step 4: Implement `get_krw_markets`**

```python
# strategy_engine/upbit_client.py
import requests

UPBIT_BASE_URL = "https://api.upbit.com/v1"


def get_krw_markets() -> list[str]:
    resp = requests.get(f"{UPBIT_BASE_URL}/market/all", params={"isDetails": "false"})
    resp.raise_for_status()
    data = resp.json()
    return [
        m["market"] for m in data
        if m["market"].startswith("KRW-") and m["market"] != "KRW-BTC"
    ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_upbit_client.py::test_get_krw_markets_filters_and_excludes_btc -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt strategy_engine/__init__.py strategy_engine/upbit_client.py tests/test_upbit_client.py
git commit -m "feat: add Upbit KRW market list client"
```

---

### Task 2: Daily candle fetching with pagination

**Files:**
- Modify: `strategy_engine/upbit_client.py`
- Test: `tests/test_upbit_client.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `upbit_client.get_daily_candles(market: str, count: int, to: str | None = None) -> pandas.DataFrame` with a `DatetimeIndex` named `date`, sorted ascending, columns `["open", "high", "low", "close", "volume"]`

- [ ] **Step 1: Write the failing test for a single page**

```python
# tests/test_upbit_client.py (append)
import pandas as pd


def _candle(date_str, o, h, l, c, v):
    return {
        "candleDateTimeKST": date_str,
        "openingPrice": o,
        "highPrice": h,
        "lowPrice": l,
        "tradePrice": c,
        "candleAccTradeVolume": v,
    }


@patch("strategy_engine.upbit_client.requests.get")
def test_get_daily_candles_single_page(mock_get):
    mock_resp = MagicMock()
    # Upbit returns newest-first
    mock_resp.json.return_value = [
        _candle("2024-01-02T00:00:00", 110, 115, 108, 112, 500),
        _candle("2024-01-01T00:00:00", 100, 105, 98, 101, 400),
    ]
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    df = upbit_client.get_daily_candles("KRW-ETH", count=2)

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.name == "date"
    assert list(df.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
    assert df.loc[pd.Timestamp("2024-01-02"), "close"] == 112
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_upbit_client.py::test_get_daily_candles_single_page -v`
Expected: FAIL with `AttributeError: module has no attribute 'get_daily_candles'`

- [ ] **Step 3: Write the failing pagination test**

```python
# tests/test_upbit_client.py (append)
import datetime


@patch("strategy_engine.upbit_client.requests.get")
def test_get_daily_candles_paginates_over_200_limit(mock_get):
    base = datetime.date(2024, 1, 1)
    all_dates_desc = [base + datetime.timedelta(days=i) for i in range(250)][::-1]  # newest first, like Upbit
    first_batch = [
        _candle(d.isoformat() + "T00:00:00", 1, 1, 1, i, 1)
        for i, d in enumerate(all_dates_desc[:200])
    ]
    second_batch = [
        _candle(d.isoformat() + "T00:00:00", 1, 1, 1, i, 1)
        for i, d in enumerate(all_dates_desc[200:250])
    ]

    resp1, resp2 = MagicMock(), MagicMock()
    resp1.json.return_value = first_batch
    resp1.raise_for_status.return_value = None
    resp2.json.return_value = second_batch
    resp2.raise_for_status.return_value = None
    mock_get.side_effect = [resp1, resp2]

    df = upbit_client.get_daily_candles("KRW-ETH", count=250)

    assert len(df) == 250
    assert df.index.is_monotonic_increasing
    assert mock_get.call_count == 2
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_upbit_client.py -v`
Expected: Both new tests FAIL (function missing)

- [ ] **Step 5: Implement `get_daily_candles`**

```python
# strategy_engine/upbit_client.py (append)
import pandas as pd


def get_daily_candles(market: str, count: int, to: str | None = None) -> pd.DataFrame:
    rows = []
    remaining = count
    cursor = to

    while remaining > 0:
        batch_size = min(remaining, 200)
        params = {"market": market, "count": batch_size}
        if cursor:
            params["to"] = cursor
        resp = requests.get(f"{UPBIT_BASE_URL}/candles/days", params=params)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        remaining -= len(batch)
        cursor = batch[-1]["candleDateTimeKST"]
        if len(batch) < batch_size:
            break

    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "candleDateTimeKST": "date",
        "openingPrice": "open",
        "highPrice": "high",
        "lowPrice": "low",
        "tradePrice": "close",
        "candleAccTradeVolume": "volume",
    })
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.set_index("date").sort_index()
    return df[["open", "high", "low", "close", "volume"]]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_upbit_client.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add strategy_engine/upbit_client.py tests/test_upbit_client.py
git commit -m "feat: add paginated daily candle fetching from Upbit"
```

---

### Task 3: Indicator functions

**Files:**
- Create: `strategy_engine/indicators.py`
- Test: `tests/test_indicators.py`

**Interfaces:**
- Produces (all take/return `pandas.Series`, aligned to the input index):
  - `sma(series, period) -> Series`
  - `rsi(series, period=14) -> Series`
  - `bollinger_band_width(series, period=20, num_std=2.0) -> Series`
  - `volume_ratio(volume, short_period=5, long_period=20) -> Series`
  - `rolling_high(series, period) -> Series`
  - `rolling_low(series, period) -> Series`
  - `pct_change_n(series, n) -> Series`
  - `ma_slope(series, period, lookback) -> Series`

- [ ] **Step 1: Write failing tests with hand-verified expected values**

```python
# tests/test_indicators.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_indicators.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'strategy_engine.indicators'`

- [ ] **Step 3: Implement `indicators.py`**

```python
# strategy_engine/indicators.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_indicators.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add strategy_engine/indicators.py tests/test_indicators.py
git commit -m "feat: add indicator functions (SMA, RSI, Bollinger width, volume ratio, etc.)"
```

---

### Task 4: Config constants

**Files:**
- Create: `strategy_engine/config.py`

**Interfaces:**
- Produces: named constants consumed by Tasks 5-9 (listed below)

- [ ] **Step 1: Create `config.py`**

```python
# strategy_engine/config.py
"""All tunable strategy thresholds. v1 defaults — tune via backtest."""

# --- Entry filter ---
HIGH_LOOKBACK_DAYS = 364              # "52-week" high/low, altcoins trade every day
RECENT_PUMP_LOOKBACK_DAYS = 14
RECENT_PUMP_RETURN_THRESHOLD = 0.30    # exclude if +30% or more over the lookback
NEAR_HIGH_THRESHOLD = 0.05             # exclude if within 5% of the 364-day high
DEEP_PULLBACK_THRESHOLD = 0.20         # confirm if 20%+ below the 364-day high
MA_SUPPORT_PERIODS = (120, 200)
MA_SUPPORT_BAND = 0.05                 # confirm if within 5% of either MA
RSI_PERIOD = 14
RSI_OVERSOLD = 30
VOLUME_RECOVERY_SHORT_PERIOD = 5
VOLUME_RECOVERY_LONG_PERIOD = 20
VOLUME_RECOVERY_RATIO = 1.5            # confirm if 5-day avg volume >= 1.5x 20-day avg
BB_PERIOD = 20
BB_STD = 2.0
BB_SQUEEZE_LOOKBACK_DAYS = 60
BB_SQUEEZE_TOLERANCE = 0.10            # "near the 60-day min" = within 10% of it

# --- Regime (downtrend) detection ---
REGIME_MA_PERIOD = 60
REGIME_SLOPE_LOOKBACK_DAYS = 5

# --- Averaging-down gates ---
AVERAGING_STEP_PCT = 0.10
MAX_AVERAGING_ROUNDS = 3
SUPPORT_LOOKBACK_DAYS = 60
SUPPORT_SURVIVAL_BAND = 0.03           # allowed if price hasn't broken more than 3% below the 60-day low
CAPITULATION_VOLUME_LOOKBACK_DAYS = 20
CAPITULATION_VOLUME_MULTIPLIER = 2.0   # a down day with 2x+ avg volume blocks averaging

# --- Exit ---
TAKE_PROFIT_PCT = 0.05

# --- Backtest position sizing (percentage-based strategy, so this only scales
# reported KRW P&L, not returns) ---
POSITION_SIZE_KRW = 100_000
```

- [ ] **Step 2: Commit**

```bash
git add strategy_engine/config.py
git commit -m "feat: add strategy engine config constants"
```

---

### Task 5: Regime detection (downtrend + dual gate)

**Files:**
- Create: `strategy_engine/regime.py`
- Test: `tests/test_regime.py`

**Interfaces:**
- Consumes: `indicators.sma`, `indicators.ma_slope`, `config.REGIME_MA_PERIOD`, `config.REGIME_SLOPE_LOOKBACK_DAYS`
- Produces:
  - `regime.is_downtrend(df: pd.DataFrame, ma_period: int = config.REGIME_MA_PERIOD, slope_lookback: int = config.REGIME_SLOPE_LOOKBACK_DAYS) -> bool`
  - `regime.is_bear_market(btc_df: pd.DataFrame, coin_df: pd.DataFrame, ma_period: int = config.REGIME_MA_PERIOD, slope_lookback: int = config.REGIME_SLOPE_LOOKBACK_DAYS) -> bool` (AND of `is_downtrend` on both, with pass-through overrides so tests can use short fixtures)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_regime.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_regime.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `regime.py`**

```python
# strategy_engine/regime.py
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
    return is_downtrend(btc_df, ma_period, slope_lookback) and is_downtrend(coin_df, ma_period, slope_lookback)
```

Note: the test cases pass `ma_period=3, slope_lookback=2` explicitly, so `is_downtrend`'s defaults (60/5) are never exercised by this test with only 10 rows — that's intentional; the defaults are exercised end-to-end in Task 9's engine tests with longer synthetic data.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_regime.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add strategy_engine/regime.py tests/test_regime.py
git commit -m "feat: add downtrend and dual-gate bear market detection"
```

---

### Task 6: Entry signal

**Files:**
- Create: `strategy_engine/entry.py`
- Test: `tests/test_entry.py`

**Interfaces:**
- Consumes: `indicators.*`, `config.*` (entry filter constants from Task 4)
- Produces:
  - `entry.is_recent_pump(df) -> bool`
  - `entry.is_near_high(df) -> bool`
  - `entry.is_deep_pullback(df) -> bool`
  - `entry.is_near_ma_support(df) -> bool`
  - `entry.is_oversold_bounce(df) -> bool`
  - `entry.is_volume_recovering(df) -> bool`
  - `entry.is_volatility_squeeze_expanding(df) -> bool`
  - `entry.entry_allowed(df) -> bool`

- [ ] **Step 1: Write failing tests for the simple predicates**

```python
# tests/test_entry.py
import pandas as pd
from unittest.mock import patch
from strategy_engine import entry


def _df(closes, volumes=None, highs=None, lows=None):
    n = len(closes)
    return pd.DataFrame({
        "close": closes,
        "high": highs or closes,
        "low": lows or closes,
        "volume": volumes or [100] * n,
    })


def test_is_recent_pump_true_when_return_exceeds_threshold():
    # flat history, then +50% in the last 14 days
    closes = [100] * 50 + [100 * (1.5 ** (i / 14)) for i in range(1, 15)]
    df = _df(closes)
    assert entry.is_recent_pump(df) is True


def test_is_recent_pump_false_when_flat():
    closes = [100] * 60
    df = _df(closes)
    assert entry.is_recent_pump(df) is False


def test_is_near_high_true_at_the_high():
    closes = list(range(1, 101))  # strictly increasing, last value is the max
    df = _df(closes)
    assert entry.is_near_high(df) is True


def test_is_near_high_false_when_far_below_high():
    closes = [100] + [50] * 99  # made a high of 100 long ago, now far below it
    df = _df(closes)
    assert entry.is_near_high(df) is False


def test_is_deep_pullback_true_after_big_drop_from_high():
    closes = [100] * 5 + [75] * 95  # 25% below the 364-day (or shorter, here 100-day) high
    df = _df(closes)
    assert entry.is_deep_pullback(df) is True


def test_is_deep_pullback_false_when_close_to_high():
    closes = [100] * 100
    df = _df(closes)
    assert entry.is_deep_pullback(df) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_entry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the simple predicates**

```python
# strategy_engine/entry.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_entry.py -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for the remaining predicates**

```python
# tests/test_entry.py (append)
def test_is_near_ma_support_true_when_close_tracks_ma():
    closes = [100] * 250  # flat: close always equals every MA
    df = _df(closes)
    assert entry.is_near_ma_support(df) is True


def test_is_near_ma_support_false_when_far_above_ma():
    # steadily rising for 250 days puts the last close well above the 120/200 MA
    closes = [100 + i * 2 for i in range(250)]
    df = _df(closes)
    assert entry.is_near_ma_support(df) is False


def test_is_oversold_bounce_true_on_rsi_bounce_from_oversold():
    # decline pushes RSI under 30, then one up day bounces it
    closes = [100 - i for i in range(30)] + [72]
    df = _df(closes)
    assert entry.is_oversold_bounce(df) is True


def test_is_oversold_bounce_false_when_rsi_is_high():
    closes = [100 + i for i in range(31)]
    df = _df(closes)
    assert entry.is_oversold_bounce(df) is False


def test_is_volume_recovering_true_when_recent_volume_spikes():
    volumes = [100] * 40 + [200] * 5
    df = _df([100] * 45, volumes=volumes)
    assert entry.is_volume_recovering(df) is True


def test_is_volume_recovering_false_when_flat():
    df = _df([100] * 45, volumes=[100] * 45)
    assert entry.is_volume_recovering(df) is False
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_entry.py -v`
Expected: The four new tests FAIL with `AttributeError`

- [ ] **Step 7: Implement the remaining predicates**

```python
# strategy_engine/entry.py (append)
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
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_entry.py -v`
Expected: All PASS

- [ ] **Step 9: Write failing test for the volatility squeeze predicate and the composition**

```python
# tests/test_entry.py (append)
def test_is_volatility_squeeze_expanding_true_after_squeeze_then_expansion():
    # low, stable volatility for a while, then a sudden expansion on the last day
    stable = [100, 101, 100, 101, 100] * 16  # 80 rows of tight, low-volatility oscillation
    df = _df(stable + [130])  # one big jump expands the band sharply
    assert entry.is_volatility_squeeze_expanding(df) is True


def test_is_volatility_squeeze_expanding_false_when_volatility_stays_flat():
    stable = [100, 101, 100, 101, 100] * 17
    df = _df(stable)
    assert entry.is_volatility_squeeze_expanding(df) is False


def test_entry_allowed_composition_table():
    df = _df([100] * 10)  # content doesn't matter, predicates are mocked below
    base_patches = {
        "is_recent_pump": False,
        "is_near_high": False,
        "is_deep_pullback": False,
        "is_near_ma_support": False,
        "is_oversold_bounce": False,
        "is_volume_recovering": False,
        "is_volatility_squeeze_expanding": False,
    }

    def run_with(**overrides):
        values = {**base_patches, **overrides}
        with patch.multiple("strategy_engine.entry", **{k: lambda df, v=v: v for k, v in values.items()}):
            return entry.entry_allowed(df)

    # no exclusions, no confirmations -> not allowed
    assert run_with() is False
    # no exclusions, one confirmation -> allowed
    assert run_with(is_deep_pullback=True) is True
    assert run_with(is_near_ma_support=True) is True
    assert run_with(is_oversold_bounce=True) is True
    assert run_with(is_volume_recovering=True) is True
    assert run_with(is_volatility_squeeze_expanding=True) is True
    # exclusion present, even with a confirmation -> not allowed
    assert run_with(is_recent_pump=True, is_deep_pullback=True) is False
    assert run_with(is_near_high=True, is_deep_pullback=True) is False
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `pytest tests/test_entry.py -v`
Expected: New tests FAIL (`AttributeError` for the squeeze predicate; composition test fails because `entry_allowed` doesn't exist)

- [ ] **Step 11: Implement the squeeze predicate and `entry_allowed`**

```python
# strategy_engine/entry.py (append)
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
```

- [ ] **Step 12: Run tests to verify they pass**

Run: `pytest tests/test_entry.py -v`
Expected: All PASS

- [ ] **Step 13: Commit**

```bash
git add strategy_engine/entry.py tests/test_entry.py
git commit -m "feat: add entry signal predicates and composition"
```

---

### Task 7: Exit (take-profit) signal

**Files:**
- Create: `strategy_engine/exit_signal.py`
- Test: `tests/test_exit_signal.py`

**Interfaces:**
- Consumes: `config.TAKE_PROFIT_PCT`
- Produces: `exit_signal.is_take_profit(avg_price: float, current_price: float, take_profit_pct: float = config.TAKE_PROFIT_PCT) -> bool`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_exit_signal.py
from strategy_engine import exit_signal


def test_is_take_profit_true_at_threshold():
    assert exit_signal.is_take_profit(avg_price=1000, current_price=1050) is True


def test_is_take_profit_true_above_threshold():
    assert exit_signal.is_take_profit(avg_price=1000, current_price=1200) is True


def test_is_take_profit_false_below_threshold():
    assert exit_signal.is_take_profit(avg_price=1000, current_price=1049) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_exit_signal.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `exit_signal.py`**

```python
# strategy_engine/exit_signal.py
from . import config


def is_take_profit(avg_price: float, current_price: float, take_profit_pct: float = config.TAKE_PROFIT_PCT) -> bool:
    return (current_price - avg_price) / avg_price >= take_profit_pct
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_exit_signal.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add strategy_engine/exit_signal.py tests/test_exit_signal.py
git commit -m "feat: add take-profit exit signal"
```

---

### Task 8: Averaging-down signal

**Files:**
- Create: `strategy_engine/averaging.py`
- Test: `tests/test_averaging.py`

**Interfaces:**
- Consumes: `indicators.*`, `regime.is_bear_market`, `config.*`
- Produces:
  - `averaging.has_reached_step(avg_price, current_price, rounds_used, step_pct=config.AVERAGING_STEP_PCT) -> bool`
  - `averaging.is_support_alive(df, band=config.SUPPORT_SURVIVAL_BAND) -> bool`
  - `averaging.is_capitulation(df) -> bool`
  - `averaging.averaging_allowed(coin_df, btc_df, avg_price, current_price, rounds_used) -> bool`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_averaging.py
import pandas as pd
from unittest.mock import patch
from strategy_engine import averaging


def _df(closes, volumes=None):
    n = len(closes)
    return pd.DataFrame({"close": closes, "volume": volumes or [100] * n})


def test_has_reached_step_true_at_first_averaging_round():
    # avg 1000, current 899 -> -10.1%, rounds_used=0 -> first averaging round threshold is -10%
    assert averaging.has_reached_step(avg_price=1000, current_price=899, rounds_used=0) is True


def test_has_reached_step_false_before_threshold():
    assert averaging.has_reached_step(avg_price=1000, current_price=910, rounds_used=0) is False


def test_has_reached_step_requires_next_step_for_second_round():
    # after 1 round used, need -20% from original avg, not just -10%
    assert averaging.has_reached_step(avg_price=1000, current_price=850, rounds_used=1) is False
    assert averaging.has_reached_step(avg_price=1000, current_price=799, rounds_used=1) is True


def test_has_reached_step_false_when_rounds_exhausted():
    # MAX_AVERAGING_ROUNDS = 3, rounds_used=3 means no more rounds allowed
    assert averaging.has_reached_step(avg_price=1000, current_price=100, rounds_used=3) is False


def test_is_support_alive_true_when_within_band_of_recent_low():
    closes = [100, 90, 80, 82, 81]  # recent low 80, current 81 (within 3%)
    df = _df(closes)
    assert averaging.is_support_alive(df) is True


def test_is_support_alive_false_when_broken_below_band():
    closes = [100, 90, 80, 82, 70]  # current 70 is far below the recent low of 80
    df = _df(closes)
    assert averaging.is_support_alive(df) is False


def test_is_capitulation_true_on_down_day_with_volume_spike():
    closes = [100] * 20 + [90]  # down day
    volumes = [100] * 20 + [250]  # 2.5x the 20-day average
    df = _df(closes, volumes)
    assert averaging.is_capitulation(df) is True


def test_is_capitulation_false_on_down_day_with_normal_volume():
    closes = [100] * 20 + [90]
    volumes = [100] * 21
    df = _df(closes, volumes)
    assert averaging.is_capitulation(df) is False


def test_is_capitulation_false_on_up_day_even_with_volume_spike():
    closes = [100] * 20 + [110]
    volumes = [100] * 20 + [250]
    df = _df(closes, volumes)
    assert averaging.is_capitulation(df) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_averaging.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the gate predicates**

```python
# strategy_engine/averaging.py
import pandas as pd
from . import config, indicators, regime


def has_reached_step(
    avg_price: float,
    current_price: float,
    rounds_used: int,
    step_pct: float = config.AVERAGING_STEP_PCT,
) -> bool:
    if rounds_used >= config.MAX_AVERAGING_ROUNDS:
        return False
    required_drop = step_pct * (rounds_used + 1)
    actual_drop = (avg_price - current_price) / avg_price
    return actual_drop >= required_drop


def is_support_alive(df: pd.DataFrame, band: float = config.SUPPORT_SURVIVAL_BAND) -> bool:
    low = indicators.rolling_low(df["close"], config.SUPPORT_LOOKBACK_DAYS)
    current = df["close"].iloc[-1]
    return bool(current >= low.iloc[-1] * (1 - band))


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_averaging.py -v`
Expected: All PASS

- [ ] **Step 5: Write failing test for `averaging_allowed` composition**

```python
# tests/test_averaging.py (append)
def test_averaging_allowed_composition_table():
    coin_df = _df([100] * 10)
    btc_df = _df([100] * 10)

    def run_with(reached=True, support=True, capitulation=False, bear=False):
        with patch("strategy_engine.averaging.has_reached_step", return_value=reached), \
             patch("strategy_engine.averaging.is_support_alive", return_value=support), \
             patch("strategy_engine.averaging.is_capitulation", return_value=capitulation), \
             patch("strategy_engine.regime.is_bear_market", return_value=bear):
            return averaging.averaging_allowed(coin_df, btc_df, avg_price=1000, current_price=900, rounds_used=0)

    assert run_with() is True
    assert run_with(reached=False) is False
    assert run_with(support=False) is False
    assert run_with(capitulation=True) is False
    assert run_with(bear=True) is False
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_averaging.py::test_averaging_allowed_composition_table -v`
Expected: FAIL with `AttributeError`

- [ ] **Step 7: Implement `averaging_allowed`**

```python
# strategy_engine/averaging.py (append)
def averaging_allowed(
    coin_df: pd.DataFrame,
    btc_df: pd.DataFrame,
    avg_price: float,
    current_price: float,
    rounds_used: int,
) -> bool:
    if not has_reached_step(avg_price, current_price, rounds_used):
        return False
    if not is_support_alive(coin_df):
        return False
    if is_capitulation(coin_df):
        return False
    if regime.is_bear_market(btc_df, coin_df):
        return False
    return True
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_averaging.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add strategy_engine/averaging.py tests/test_averaging.py
git commit -m "feat: add averaging-down gates and composition"
```

---

### Task 9: Portfolio / position state

**Files:**
- Create: `strategy_engine/portfolio.py`
- Test: `tests/test_portfolio.py`

**Interfaces:**
- Produces:
  - `Position` (dataclass: `market: str`, `entries: list[dict]`; properties `rounds_used`, `total_qty`, `avg_price`)
  - `ClosedTrade` (dataclass: `market`, `avg_price`, `exit_price`, `qty`, `entry_date`, `exit_date`; property `pnl`)
  - `Portfolio(position_size_krw: float)` with `is_held`, `open_position`, `add_to_position`, `close_position`, `.positions: dict[str, Position]`, `.closed_trades: list[ClosedTrade]`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_portfolio.py
import pytest
from strategy_engine.portfolio import Portfolio


def test_open_position_sets_avg_price_and_qty():
    p = Portfolio(position_size_krw=100_000)
    p.open_position("KRW-ETH", price=1000, trade_date="2024-01-01")

    position = p.positions["KRW-ETH"]
    assert position.avg_price == pytest.approx(1000)
    assert position.total_qty == pytest.approx(100)
    assert position.rounds_used == 0
    assert p.is_held("KRW-ETH") is True
    assert p.is_held("KRW-XRP") is False


def test_add_to_position_updates_weighted_avg_price():
    p = Portfolio(position_size_krw=100_000)
    p.open_position("KRW-ETH", price=1000, trade_date="2024-01-01")
    p.add_to_position("KRW-ETH", price=900, trade_date="2024-01-02")

    position = p.positions["KRW-ETH"]
    # 100000 @1000 -> 100 qty; 100000 @900 -> 111.111 qty
    # avg = 200000 / 211.111 = 947.368...
    assert position.total_qty == pytest.approx(211.111, abs=0.01)
    assert position.avg_price == pytest.approx(947.368, abs=0.01)
    assert position.rounds_used == 1


def test_close_position_records_closed_trade_and_removes_position():
    p = Portfolio(position_size_krw=100_000)
    p.open_position("KRW-ETH", price=1000, trade_date="2024-01-01")
    p.add_to_position("KRW-ETH", price=900, trade_date="2024-01-02")

    trade = p.close_position("KRW-ETH", price=1000, trade_date="2024-01-10")

    assert p.is_held("KRW-ETH") is False
    assert trade in p.closed_trades
    assert trade.pnl == pytest.approx(11111.11, abs=0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_portfolio.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `portfolio.py`**

```python
# strategy_engine/portfolio.py
from dataclasses import dataclass, field


@dataclass
class Position:
    market: str
    entries: list = field(default_factory=list)

    @property
    def rounds_used(self) -> int:
        return len(self.entries) - 1

    @property
    def total_qty(self) -> float:
        return sum(e["qty"] for e in self.entries)

    @property
    def avg_price(self) -> float:
        total_cost = sum(e["price"] * e["qty"] for e in self.entries)
        return total_cost / self.total_qty


@dataclass
class ClosedTrade:
    market: str
    avg_price: float
    exit_price: float
    qty: float
    entry_date: object
    exit_date: object

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.avg_price) * self.qty


class Portfolio:
    def __init__(self, position_size_krw: float):
        self.position_size_krw = position_size_krw
        self.positions: dict[str, Position] = {}
        self.closed_trades: list[ClosedTrade] = []

    def is_held(self, market: str) -> bool:
        return market in self.positions

    def open_position(self, market: str, price: float, trade_date) -> None:
        qty = self.position_size_krw / price
        self.positions[market] = Position(market=market, entries=[{"date": trade_date, "price": price, "qty": qty}])

    def add_to_position(self, market: str, price: float, trade_date) -> None:
        qty = self.position_size_krw / price
        self.positions[market].entries.append({"date": trade_date, "price": price, "qty": qty})

    def close_position(self, market: str, price: float, trade_date) -> ClosedTrade:
        position = self.positions.pop(market)
        trade = ClosedTrade(
            market=market,
            avg_price=position.avg_price,
            exit_price=price,
            qty=position.total_qty,
            entry_date=position.entries[0]["date"],
            exit_date=trade_date,
        )
        self.closed_trades.append(trade)
        return trade
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_portfolio.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add strategy_engine/portfolio.py tests/test_portfolio.py
git commit -m "feat: add Position/ClosedTrade/Portfolio state model"
```

---

### Task 10: Daily engine orchestration

**Files:**
- Create: `strategy_engine/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `entry.entry_allowed`, `exit_signal.is_take_profit`, `averaging.averaging_allowed`, `regime.is_downtrend`, `portfolio.Portfolio`, `config.TAKE_PROFIT_PCT`
- Produces: `engine.run_daily_cycle(portfolio: Portfolio, market_data: dict[str, pd.DataFrame], btc_df: pd.DataFrame, trade_date) -> list[dict]` — each dict has at least `{"type": "take_profit" | "averaging" | "entry" | "danger_warning", "market": str}`

Per `prompt/strategy_topic.md` §3-2 signal 5 ("위험선 경고"), a held position whose own trend has structurally broken (`regime.is_downtrend(coin_df)` true) is flagged with a `danger_warning` action every cycle it stays broken — this is informational only, it never blocks or forces a sell.

- [ ] **Step 1: Write failing tests using mocked signal functions**

```python
# tests/test_engine.py
import pandas as pd
from unittest.mock import patch
from strategy_engine import engine
from strategy_engine.portfolio import Portfolio


def _df():
    return pd.DataFrame({"close": [100] * 10, "volume": [100] * 10})


def test_take_profit_closes_held_position():
    portfolio = Portfolio(position_size_krw=100_000)
    portfolio.open_position("KRW-ETH", price=1000, trade_date="d0")
    market_data = {"KRW-ETH": _df()}

    with patch("strategy_engine.engine.is_take_profit", return_value=True), \
         patch("strategy_engine.engine.averaging_allowed", return_value=False), \
         patch("strategy_engine.engine.entry_allowed", return_value=False):
        actions = engine.run_daily_cycle(portfolio, market_data, _df(), trade_date="d1")

    assert portfolio.is_held("KRW-ETH") is False
    assert actions == [{"type": "take_profit", "market": "KRW-ETH", "trade": portfolio.closed_trades[0]}]


def test_averaging_skips_new_entry_scan_this_cycle():
    portfolio = Portfolio(position_size_krw=100_000)
    portfolio.open_position("KRW-ETH", price=1000, trade_date="d0")
    market_data = {"KRW-ETH": _df(), "KRW-XRP": _df()}

    with patch("strategy_engine.engine.is_take_profit", return_value=False), \
         patch("strategy_engine.engine.averaging_allowed", return_value=True), \
         patch("strategy_engine.engine.entry_allowed", return_value=True) as mock_entry:
        actions = engine.run_daily_cycle(portfolio, market_data, _df(), trade_date="d1")

    assert portfolio.positions["KRW-ETH"].rounds_used == 1
    assert portfolio.is_held("KRW-XRP") is False  # entry scan was skipped
    mock_entry.assert_not_called()
    assert {"type": "averaging", "market": "KRW-ETH"} in actions


def test_new_entry_when_nothing_to_take_profit_or_average():
    portfolio = Portfolio(position_size_krw=100_000)
    market_data = {"KRW-ETH": _df()}

    with patch("strategy_engine.engine.is_take_profit", return_value=False), \
         patch("strategy_engine.engine.averaging_allowed", return_value=False), \
         patch("strategy_engine.engine.entry_allowed", return_value=True):
        actions = engine.run_daily_cycle(portfolio, market_data, _df(), trade_date="d1")

    assert portfolio.is_held("KRW-ETH") is True
    assert {"type": "entry", "market": "KRW-ETH"} in actions


def test_danger_warning_flagged_for_held_position_in_individual_downtrend():
    portfolio = Portfolio(position_size_krw=100_000)
    portfolio.open_position("KRW-ETH", price=1000, trade_date="d0")
    market_data = {"KRW-ETH": _df()}

    with patch("strategy_engine.engine.is_take_profit", return_value=False), \
         patch("strategy_engine.engine.averaging_allowed", return_value=False), \
         patch("strategy_engine.engine.entry_allowed", return_value=False), \
         patch("strategy_engine.engine.is_downtrend", return_value=True):
        actions = engine.run_daily_cycle(portfolio, market_data, _df(), trade_date="d1")

    assert portfolio.is_held("KRW-ETH") is True  # warning never forces a sell
    assert {"type": "danger_warning", "market": "KRW-ETH"} in actions


def test_no_danger_warning_when_individual_trend_is_fine():
    portfolio = Portfolio(position_size_krw=100_000)
    portfolio.open_position("KRW-ETH", price=1000, trade_date="d0")
    market_data = {"KRW-ETH": _df()}

    with patch("strategy_engine.engine.is_take_profit", return_value=False), \
         patch("strategy_engine.engine.averaging_allowed", return_value=False), \
         patch("strategy_engine.engine.entry_allowed", return_value=False), \
         patch("strategy_engine.engine.is_downtrend", return_value=False):
        actions = engine.run_daily_cycle(portfolio, market_data, _df(), trade_date="d1")

    assert actions == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `engine.py`**

```python
# strategy_engine/engine.py
import pandas as pd
from .entry import entry_allowed
from .exit_signal import is_take_profit
from .averaging import averaging_allowed
from .regime import is_downtrend
from .portfolio import Portfolio


def run_daily_cycle(
    portfolio: Portfolio,
    market_data: dict,
    btc_df: pd.DataFrame,
    trade_date,
) -> list:
    actions = []

    for market in list(portfolio.positions.keys()):
        df = market_data[market]
        position = portfolio.positions[market]
        current_price = df["close"].iloc[-1]
        if is_take_profit(position.avg_price, current_price):
            trade = portfolio.close_position(market, current_price, trade_date)
            actions.append({"type": "take_profit", "market": market, "trade": trade})

    averaged_any = False
    for market in list(portfolio.positions.keys()):
        df = market_data[market]
        position = portfolio.positions[market]
        current_price = df["close"].iloc[-1]
        if averaging_allowed(df, btc_df, position.avg_price, current_price, position.rounds_used):
            portfolio.add_to_position(market, current_price, trade_date)
            averaged_any = True
            actions.append({"type": "averaging", "market": market})

    if not averaged_any:
        for market, df in market_data.items():
            if portfolio.is_held(market):
                continue
            if entry_allowed(df):
                current_price = df["close"].iloc[-1]
                portfolio.open_position(market, current_price, trade_date)
                actions.append({"type": "entry", "market": market})

    # Informational only — never blocks or forces a sell (prompt/strategy_topic.md §3-2, signal 5)
    for market in portfolio.positions:
        if is_downtrend(market_data[market]):
            actions.append({"type": "danger_warning", "market": market})

    return actions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_engine.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add strategy_engine/engine.py tests/test_engine.py
git commit -m "feat: add daily engine orchestration with take-profit/averaging/entry priority"
```

---

### Task 11: Backtest metrics

**Files:**
- Create: `strategy_engine/backtest/__init__.py`
- Create: `strategy_engine/backtest/metrics.py`
- Test: `tests/test_backtest_metrics.py`

**Interfaces:**
- Consumes: `portfolio.ClosedTrade`
- Produces: `metrics.compute_metrics(closed_trades: list[ClosedTrade]) -> dict` with keys `num_trades`, `total_pnl`, `win_rate`, `total_return_pct`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_backtest_metrics.py
import pytest
from strategy_engine.portfolio import ClosedTrade
from strategy_engine.backtest.metrics import compute_metrics


def test_compute_metrics_empty():
    result = compute_metrics([])
    assert result == {"num_trades": 0, "total_pnl": 0.0, "win_rate": 0.0, "total_return_pct": 0.0}


def test_compute_metrics_mixed_trades():
    trades = [
        ClosedTrade(market="KRW-ETH", avg_price=1000, exit_price=1050, qty=100, entry_date="d0", exit_date="d1"),
        ClosedTrade(market="KRW-XRP", avg_price=500, exit_price=450, qty=200, entry_date="d0", exit_date="d1"),
    ]
    # trade 1 pnl = (1050-1000)*100 = 5000, invested 100000
    # trade 2 pnl = (450-500)*200 = -10000, invested 100000
    result = compute_metrics(trades)

    assert result["num_trades"] == 2
    assert result["total_pnl"] == pytest.approx(-5000)
    assert result["win_rate"] == pytest.approx(0.5)
    assert result["total_return_pct"] == pytest.approx(-5000 / 200000)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backtest_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `metrics.py`**

```python
# strategy_engine/backtest/metrics.py
from strategy_engine.portfolio import ClosedTrade


def compute_metrics(closed_trades: list) -> dict:
    if not closed_trades:
        return {"num_trades": 0, "total_pnl": 0.0, "win_rate": 0.0, "total_return_pct": 0.0}

    total_pnl = sum(t.pnl for t in closed_trades)
    wins = sum(1 for t in closed_trades if t.pnl > 0)
    total_invested = sum(t.avg_price * t.qty for t in closed_trades)

    return {
        "num_trades": len(closed_trades),
        "total_pnl": total_pnl,
        "win_rate": wins / len(closed_trades),
        "total_return_pct": total_pnl / total_invested if total_invested else 0.0,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_backtest_metrics.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add strategy_engine/backtest/__init__.py strategy_engine/backtest/metrics.py tests/test_backtest_metrics.py
git commit -m "feat: add backtest performance metrics"
```

---

### Task 12: Backtest runner

**Files:**
- Create: `strategy_engine/backtest/runner.py`
- Test: `tests/test_backtest_runner.py`

**Interfaces:**
- Consumes: `engine.run_daily_cycle`, `portfolio.Portfolio`, `backtest.metrics.compute_metrics`, `config.POSITION_SIZE_KRW`
- Produces: `runner.run_backtest(btc_df: pd.DataFrame, market_data: dict[str, pd.DataFrame], start_date, end_date) -> dict` with keys `actions`, `metrics`, `open_positions`

- [ ] **Step 1: Write failing test using a stubbed `run_daily_cycle`**

```python
# tests/test_backtest_runner.py
import pandas as pd
from unittest.mock import patch
from strategy_engine.backtest.runner import run_backtest


def _dated_df(dates):
    return pd.DataFrame({"close": [100] * len(dates)}, index=pd.DatetimeIndex(dates, name="date"))


def test_run_backtest_calls_daily_cycle_once_per_date_in_range():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    btc_df = _dated_df(dates)
    market_data = {"KRW-ETH": _dated_df(dates)}

    call_dates = []

    def fake_run_daily_cycle(portfolio, day_market_data, btc_slice, trade_date):
        call_dates.append(trade_date)
        return [{"type": "entry", "market": "KRW-ETH"}] if trade_date == dates[0] else []

    with patch("strategy_engine.backtest.runner.run_daily_cycle", side_effect=fake_run_daily_cycle):
        result = run_backtest(btc_df, market_data, start_date=dates[0], end_date=dates[-1])

    assert call_dates == list(dates)
    assert {"type": "entry", "market": "KRW-ETH"} in result["actions"]
    assert "metrics" in result
    assert "open_positions" in result


def test_run_backtest_restricts_dates_to_the_given_range():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    btc_df = _dated_df(dates)
    market_data = {"KRW-ETH": _dated_df(dates)}

    call_dates = []

    def fake_run_daily_cycle(portfolio, day_market_data, btc_slice, trade_date):
        call_dates.append(trade_date)
        return []

    with patch("strategy_engine.backtest.runner.run_daily_cycle", side_effect=fake_run_daily_cycle):
        run_backtest(btc_df, market_data, start_date=dates[2], end_date=dates[5])

    assert call_dates == list(dates[2:6])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backtest_runner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `runner.py`**

```python
# strategy_engine/backtest/runner.py
import pandas as pd
from strategy_engine import config
from strategy_engine.portfolio import Portfolio
from strategy_engine.engine import run_daily_cycle
from strategy_engine.backtest.metrics import compute_metrics


def run_backtest(btc_df: pd.DataFrame, market_data: dict, start_date, end_date) -> dict:
    portfolio = Portfolio(position_size_krw=config.POSITION_SIZE_KRW)
    all_actions = []

    dates = [d for d in btc_df.index if start_date <= d <= end_date]

    for trade_date in dates:
        btc_slice = btc_df.loc[:trade_date]
        day_market_data = {
            market: df.loc[:trade_date]
            for market, df in market_data.items()
            if not df.loc[:trade_date].empty
        }
        actions = run_daily_cycle(portfolio, day_market_data, btc_slice, trade_date)
        all_actions.extend(actions)

    return {
        "actions": all_actions,
        "metrics": compute_metrics(portfolio.closed_trades),
        "open_positions": list(portfolio.positions.keys()),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_backtest_runner.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add strategy_engine/backtest/runner.py tests/test_backtest_runner.py
git commit -m "feat: add backtest runner iterating the engine over historical dates"
```

---

### Task 13: CLI script to run a real backtest

**Files:**
- Create: `strategy_engine/scripts/__init__.py`
- Create: `strategy_engine/scripts/run_backtest.py`

**Interfaces:**
- Consumes: `upbit_client.get_krw_markets`, `upbit_client.get_daily_candles`, `backtest.runner.run_backtest`, `config.HIGH_LOOKBACK_DAYS`

- [ ] **Step 1: Implement the CLI script**

No new unit test here — this wires already-tested pieces to real network calls, which is best verified by running it manually against the live Upbit API (Step 2).

```python
# strategy_engine/scripts/run_backtest.py
import argparse
import sys

import pandas as pd

from strategy_engine import config, upbit_client
from strategy_engine.backtest.runner import run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the altcoin strategy engine backtest against live Upbit history.")
    parser.add_argument("--days", type=int, default=730, help="How many days of history to fetch per market.")
    parser.add_argument("--markets", nargs="*", default=None, help="Specific KRW-* markets to test; defaults to all.")
    args = parser.parse_args()

    fetch_count = max(args.days, config.HIGH_LOOKBACK_DAYS + 30)

    print("Fetching BTC reference data...", file=sys.stderr)
    btc_df = upbit_client.get_daily_candles("KRW-BTC", count=fetch_count)

    markets = args.markets or upbit_client.get_krw_markets()
    market_data = {}
    for market in markets:
        print(f"Fetching {market}...", file=sys.stderr)
        market_data[market] = upbit_client.get_daily_candles(market, count=fetch_count)

    start_date = btc_df.index[config.HIGH_LOOKBACK_DAYS]
    end_date = btc_df.index[-1]

    result = run_backtest(btc_df, market_data, start_date=start_date, end_date=end_date)

    print(f"\nBacktest period: {start_date.date()} to {end_date.date()}")
    print(f"Markets tested: {len(markets)}")
    print(f"Total actions: {len(result['actions'])}")
    print(f"Open positions at end: {result['open_positions']}")
    print("Metrics:")
    for key, value in result["metrics"].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it manually against live data**

Run: `python -m strategy_engine.scripts.run_backtest --markets KRW-ETH KRW-XRP --days 730`
Expected: Prints fetch progress to stderr, then a metrics summary to stdout with no exceptions. Note in the PR/commit message what the sample output was, but treat any actual return numbers as informational only — thresholds are v1 defaults, not yet validated.

- [ ] **Step 3: Commit**

```bash
git add strategy_engine/scripts/__init__.py strategy_engine/scripts/run_backtest.py
git commit -m "feat: add CLI script to run the strategy engine backtest against live Upbit data"
```

---

## Post-plan open items (not covered by this plan)

These are explicitly deferred, per `prompt/strategy_topic.md` section 5 and the brainstorming discussion:

- Daily vs. weekly candle basis — compare via backtest once this plan is implemented (swap `HIGH_LOOKBACK_DAYS` and every other day-based constant for a week-based equivalent and re-run `run_backtest`).
- Tuning every threshold in `config.py` against real backtest results — the values here are v1 starting points, not validated.
- Live order execution, MySQL persistence, and monitoring/alerting are separate sub-projects per the original decomposition and are not part of this plan.
