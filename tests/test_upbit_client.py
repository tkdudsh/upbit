from unittest.mock import patch, MagicMock
from strategy_engine import upbit_client
import pandas as pd
import datetime


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


def _candle(date_str, o, h, l, c, v):
    # Field names match Upbit's real /v1/candles/days response (snake_case),
    # not the camelCase originally (incorrectly) assumed. See the NOTE in
    # strategy_engine/upbit_client.py.
    # `candle_date_time_utc` is what pagination's `to` cursor must use (Upbit
    # interprets `to` as UTC). The same string is reused for both fields here:
    # the real 9-hour offset is irrelevant to these tests, what matters is that
    # the client reads the right JSON key.
    return {
        "candle_date_time_kst": date_str,
        "candle_date_time_utc": date_str,
        "opening_price": o,
        "high_price": h,
        "low_price": l,
        "trade_price": c,
        "candle_acc_trade_volume": v,
    }


@patch("strategy_engine.upbit_client.requests.get")
def test_get_daily_candles_single_page(mock_get):
    mock_resp = MagicMock()
    # Upbit returns newest-first
    mock_resp.json.return_value = [
        _candle("2024-01-02T09:00:00", 110, 115, 108, 112, 500),
        _candle("2024-01-01T09:00:00", 100, 105, 98, 101, 400),
    ]
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    df = upbit_client.get_daily_candles("KRW-ETH", count=2)

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.name == "date"
    assert list(df.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
    assert df.loc[pd.Timestamp("2024-01-02"), "close"] == 112


@patch("strategy_engine.upbit_client.requests.get")
def test_get_daily_candles_paginates_over_200_limit(mock_get):
    base = datetime.date(2024, 1, 1)
    all_dates_desc = [base + datetime.timedelta(days=i) for i in range(250)][::-1]  # newest first, like Upbit
    first_batch = [
        _candle(d.isoformat() + "T09:00:00", 1, 1, 1, i, 1)
        for i, d in enumerate(all_dates_desc[:200])
    ]
    second_batch = [
        _candle(d.isoformat() + "T09:00:00", 1, 1, 1, i, 1)
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


@patch("strategy_engine.upbit_client.requests.get")
def test_get_daily_candles_paginate_cursor_uses_utc_field(mock_get):
    base = datetime.date(2024, 1, 1)
    all_dates_desc = [base + datetime.timedelta(days=i) for i in range(250)][::-1]

    def _real_candle(d, i):
        # KST is 9h ahead of UTC: the KST 09:00 candle is the UTC 00:00 candle.
        return {
            "candle_date_time_kst": d.isoformat() + "T09:00:00",
            "candle_date_time_utc": d.isoformat() + "T00:00:00",
            "opening_price": 1, "high_price": 1, "low_price": 1,
            "trade_price": i, "candle_acc_trade_volume": 1,
        }

    first_batch = [_real_candle(d, i) for i, d in enumerate(all_dates_desc[:200])]
    second_batch = [_real_candle(d, i) for i, d in enumerate(all_dates_desc[200:250])]

    resp1, resp2 = MagicMock(), MagicMock()
    resp1.json.return_value = first_batch
    resp1.raise_for_status.return_value = None
    resp2.json.return_value = second_batch
    resp2.raise_for_status.return_value = None
    mock_get.side_effect = [resp1, resp2]

    upbit_client.get_daily_candles("KRW-ETH", count=250)

    # The second page's `to` cursor must be the UTC timestamp, not the KST one.
    second_call_params = mock_get.call_args_list[1].kwargs["params"]
    assert second_call_params["to"] == all_dates_desc[199].isoformat() + "T00:00:00"


@patch("strategy_engine.upbit_client.requests.get")
def test_get_daily_candles_dedups_overlapping_page_boundary(mock_get):
    # Simulates the real off-by-one: page 2's newest row repeats page 1's
    # oldest row, so the raw concatenation has one duplicated date.
    base = datetime.date(2024, 1, 1)
    all_dates_desc = [base + datetime.timedelta(days=i) for i in range(250)][::-1]
    first_batch = [
        _candle(d.isoformat() + "T09:00:00", 1, 1, 1, i, 1)
        for i, d in enumerate(all_dates_desc[:200])
    ]
    # page 2 starts by repeating page 1's last (oldest) candle
    second_batch = [
        _candle(d.isoformat() + "T09:00:00", 1, 1, 1, i, 1)
        for i, d in enumerate(all_dates_desc[199:249])
    ]

    resp1, resp2 = MagicMock(), MagicMock()
    resp1.json.return_value = first_batch
    resp1.raise_for_status.return_value = None
    resp2.json.return_value = second_batch
    resp2.raise_for_status.return_value = None
    mock_get.side_effect = [resp1, resp2]

    df = upbit_client.get_daily_candles("KRW-ETH", count=250)

    assert df.index.is_unique
    # 200 + 50 raw rows, one of which is a duplicate date -> 249 unique days
    assert len(df) == 249
    assert df.index.is_monotonic_increasing
