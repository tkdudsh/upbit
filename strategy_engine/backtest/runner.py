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
    day_market_data = {}

    for trade_date in dates:
        btc_slice = btc_df.loc[:trade_date]
        # `not df.loc[:trade_date].empty` only excluded markets that had not
        # started trading yet: a delisted/halted market keeps a non-empty prefix
        # forever, so the engine went on reading its last-ever close as "today's
        # price" indefinitely — including opening new positions in a dead
        # market. Require an actual candle on this exact date instead.
        day_market_data = {
            market: df.loc[:trade_date]
            for market, df in market_data.items()
            if trade_date in df.index
        }
        actions = run_daily_cycle(portfolio, day_market_data, btc_slice, trade_date)
        all_actions.extend(actions)

    # Mark still-open positions to market at their last price as of end_date,
    # taken from the final iteration's already-sliced day_market_data. Without
    # this, metrics would only ever see take-profit exits — every one a winner.
    # NOTE: a position whose market has no candle on end_date itself (e.g. it
    # delisted before the backtest window closed) is silently excluded here —
    # compute_metrics skips positions missing from current_prices — so its
    # unrealized loss never reaches total_return_pct. Known gap; whether to
    # force-close at the last known price on delisting is a strategy decision,
    # not something this runner should decide unilaterally.
    final_prices = {
        market: df["close"].iloc[-1]
        for market, df in day_market_data.items()
        if market in portfolio.positions
    }

    return {
        "actions": all_actions,
        "metrics": compute_metrics(
            portfolio.closed_trades,
            open_positions=list(portfolio.positions.values()),
            current_prices=final_prices,
        ),
        "open_positions": list(portfolio.positions.keys()),
    }
