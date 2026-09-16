import time

import requests
import pandas as pd

UPBIT_BASE_URL = "https://api.upbit.com/v1"

# Upbit throttles public REST calls per-IP and returns 429 when exceeded; 5xx
# also shows up transiently. Fetching a few hundred markets x 2 pages each is
# well into that territory, so pace the requests and retry the retryable codes.
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
MAX_RETRIES = 3
PAGE_DELAY_SECONDS = 0.1


def _get(url: str, params: dict) -> requests.Response:
    """GET with a small bounded retry + exponential backoff on 429/5xx."""
    for attempt in range(MAX_RETRIES):
        resp = requests.get(url, params=params)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            if resp.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise
        return resp
    return resp


def get_krw_markets() -> list[str]:
    resp = _get(f"{UPBIT_BASE_URL}/market/all", params={"isDetails": "false"})
    data = resp.json()
    return [
        m["market"] for m in data
        if m["market"].startswith("KRW-") and m["market"] != "KRW-BTC"
    ]


def get_daily_candles(market: str, count: int, to: str | None = None) -> pd.DataFrame:
    rows = []
    remaining = count
    cursor = to
    first_page = True

    while remaining > 0:
        if not first_page:
            time.sleep(PAGE_DELAY_SECONDS)
        first_page = False
        batch_size = min(remaining, 200)
        params = {"market": market, "count": batch_size}
        if cursor:
            params["to"] = cursor
        resp = _get(f"{UPBIT_BASE_URL}/candles/days", params=params)
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        remaining -= len(batch)
        # Upbit interprets the `to` query param as a UTC timestamp, so the
        # cursor must come from `candle_date_time_utc`. Using the KST field
        # (9 hours ahead) makes the next page start 9 hours "late", which on a
        # daily candle series re-returns the boundary candle: verified live, a
        # 394-row request came back with 393 unique dates and 2026-03-01 twice.
        cursor = batch[-1]["candle_date_time_utc"]
        if len(batch) < batch_size:
            break

    if not rows:
        # An unknown market code or a market with zero history returns []. A
        # bare pd.DataFrame([]) has no columns, so df["date"] below would raise
        # an opaque KeyError: 'date'. Return the right shape instead so callers
        # see an ordinary empty frame.
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            index=pd.DatetimeIndex([], name="date"),
        )

    df = pd.DataFrame(rows)
    # NOTE: Upbit's `/v1/candles/days` response uses snake_case field names
    # (e.g. `candle_date_time_kst`, `opening_price`), not the camelCase names
    # originally assumed here (`candleDateTimeKST`, `openingPrice`, ...).
    # The unit tests in tests/test_upbit_client.py mocked the camelCase
    # (incorrect) shape, so this went undetected until Task 13's first real
    # network call against api.upbit.com raised `KeyError: 'candleDateTimeKST'`.
    # Fixed here to match the real API; tests updated to match.
    df = df.rename(columns={
        "candle_date_time_kst": "date",
        "opening_price": "open",
        "high_price": "high",
        "low_price": "low",
        "trade_price": "close",
        "candle_acc_trade_volume": "volume",
    })
    # NOTE: The brief specifies `pd.to_datetime(df["date"]).dt.normalize()`.
    # On this environment (Windows, pandas 3.0.4, numpy 2.2.6), that call
    # reliably segfaults with a Windows access violation inside
    # pandas/core/arrays/datetimelike.py `_with_freq` (called from
    # `DatetimeArray.normalize`) for datetime64[us] series of length >= 3.
    # `.dt.floor("D")` was tried as an alternative and crashes identically
    # (same `_with_freq`/`_round` code path). See task-2-report.md for the
    # full repro, traceback, and version info.
    # `pd.to_datetime(...).dt.date` followed by `pd.to_datetime(...)` avoids
    # that code path entirely (it round-trips through Python `date` objects
    # instead of calling the buggy array-level freq/rounding machinery) and
    # is behaviorally equivalent: it truncates each timestamp to midnight.
    df["date"] = pd.to_datetime(pd.to_datetime(df["date"]).dt.date)
    df = df.set_index("date").sort_index()
    # Belt-and-braces: even with a correct cursor, any pagination overlap would
    # silently double-count a day in every downstream indicator. Keep the first
    # (chronologically earliest-fetched) occurrence of each date.
    df = df[~df.index.duplicated(keep="first")]
    return df[["open", "high", "low", "close", "volume"]]
