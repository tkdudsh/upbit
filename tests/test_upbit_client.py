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
