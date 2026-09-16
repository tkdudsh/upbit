import requests
import pandas as pd

UPBIT_BASE_URL = "https://api.upbit.com/v1"


def get_krw_markets() -> list[str]:
    resp = requests.get(f"{UPBIT_BASE_URL}/market/all", params={"isDetails": "false"})
    resp.raise_for_status()
    data = resp.json()
    return [
        m["market"] for m in data
        if m["market"].startswith("KRW-") and m["market"] != "KRW-BTC"
    ]


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
    return df[["open", "high", "low", "close", "volume"]]
