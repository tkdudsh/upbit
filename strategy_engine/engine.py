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
    # Markets closed by take-profit in THIS cycle. Once closed, is_held() goes
    # False, so without this the entry scan below would re-evaluate the very
    # same market and could re-buy it at the identical close it was just sold
    # at. This is a per-market skip, independent of the whole-scan "something
    # was averaged" rule.
    closed_this_cycle = set()

    for market in list(portfolio.positions.keys()):
        df = market_data[market]
        position = portfolio.positions[market]
        current_price = df["close"].iloc[-1]
        if is_take_profit(position.avg_price, current_price):
            trade = portfolio.close_position(market, current_price, trade_date)
            closed_this_cycle.add(market)
            actions.append({"type": "take_profit", "market": market, "trade": trade})

    averaged_any = False
    for market in list(portfolio.positions.keys()):
        df = market_data[market]
        position = portfolio.positions[market]
        current_price = df["close"].iloc[-1]
        # entry_price, not avg_price: the ladder's -10%/-20%/-30% steps must be
        # measured against a fixed reference. avg_price moves down after every
        # round, so each threshold would be checked against an already-lowered
        # target and the ladder would overshoot its documented -30% envelope.
        if averaging_allowed(df, btc_df, position.entry_price, current_price, position.rounds_used):
            portfolio.add_to_position(market, current_price, trade_date)
            averaged_any = True
            actions.append({"type": "averaging", "market": market})

    if not averaged_any:
        for market, df in market_data.items():
            if portfolio.is_held(market):
                continue
            if market in closed_this_cycle:
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
