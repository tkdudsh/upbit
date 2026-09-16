import argparse
import sys

import pandas as pd

from strategy_engine import config, upbit_client
from strategy_engine.backtest.runner import run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the altcoin strategy engine backtest against live Upbit history.")
    parser.add_argument("--days", type=int, default=730, help="How many days of history to fetch per market.")
    parser.add_argument("--markets", nargs="*", default=None, help="Specific KRW-* markets to test; defaults to all.")
    args = parser.parse_args()

    fetch_count = max(args.days, config.HIGH_LOOKBACK_DAYS + 30)

    print("Fetching BTC reference data...", file=sys.stderr)
    btc_df = upbit_client.get_daily_candles("KRW-BTC", count=fetch_count)

    markets = args.markets or upbit_client.get_krw_markets()
    market_data = {}
    for market in markets:
        print(f"Fetching {market}...", file=sys.stderr)
        market_data[market] = upbit_client.get_daily_candles(market, count=fetch_count)

    start_date = btc_df.index[config.HIGH_LOOKBACK_DAYS]
    end_date = btc_df.index[-1]

    result = run_backtest(btc_df, market_data, start_date=start_date, end_date=end_date)

    print(f"\nBacktest period: {start_date.date()} to {end_date.date()}")
    print(f"Markets tested: {len(markets)}")
    print(f"Total actions: {len(result['actions'])}")
    print(f"Open positions at end: {result['open_positions']}")
    print("Metrics:")
    for key, value in result["metrics"].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
