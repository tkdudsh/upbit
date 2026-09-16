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
