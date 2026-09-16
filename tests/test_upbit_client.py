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
