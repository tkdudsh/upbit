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


def test_run_backtest_excludes_markets_with_no_candle_for_that_date():
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    btc_df = _dated_df(dates)
    market_data = {
        "KRW-ETH": _dated_df(dates),
        "KRW-DEAD": _dated_df(dates[:3]),   # delisted after day 3
        "KRW-LATE": _dated_df(dates[4:]),   # only listed from day 5
    }

    seen = []

    def fake_run_daily_cycle(portfolio, day_market_data, btc_slice, trade_date):
        seen.append((trade_date, sorted(day_market_data)))
        return []

    with patch("strategy_engine.backtest.runner.run_daily_cycle", side_effect=fake_run_daily_cycle):
        run_backtest(btc_df, market_data, start_date=dates[0], end_date=dates[-1])

    by_date = dict(seen)
    assert by_date[dates[0]] == ["KRW-DEAD", "KRW-ETH"]
    assert by_date[dates[2]] == ["KRW-DEAD", "KRW-ETH"]
    # A delisted market must not linger on its last-ever close forever.
    assert by_date[dates[3]] == ["KRW-ETH"]
    assert by_date[dates[4]] == ["KRW-ETH", "KRW-LATE"]
