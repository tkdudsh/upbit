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
