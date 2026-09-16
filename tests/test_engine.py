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


def test_take_profit_market_is_not_re_entered_in_the_same_cycle():
    portfolio = Portfolio(position_size_krw=100_000)
    portfolio.open_position("KRW-ETH", price=1000, trade_date="d0")
    market_data = {"KRW-ETH": _df(), "KRW-XRP": _df()}

    with patch("strategy_engine.engine.is_take_profit", return_value=True), \
         patch("strategy_engine.engine.averaging_allowed", return_value=False), \
         patch("strategy_engine.engine.entry_allowed", return_value=True), \
         patch("strategy_engine.engine.is_downtrend", return_value=False):
        actions = engine.run_daily_cycle(portfolio, market_data, _df(), trade_date="d1")

    # sold this cycle -> must not be bought back at the same close
    assert portfolio.is_held("KRW-ETH") is False
    assert {"type": "entry", "market": "KRW-ETH"} not in actions
    # other markets are still open to new entries as normal
    assert portfolio.is_held("KRW-XRP") is True
    assert {"type": "entry", "market": "KRW-XRP"} in actions


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
