import argparse
import sys

from strategy_engine import config, upbit_client
from strategy_engine.backtest.runner import run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the altcoin strategy engine backtest against live Upbit history.")
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help=(
            "Number of days in the backtest window itself, excluding indicator "
            f"warm-up history. An extra {config.HIGH_LOOKBACK_DAYS} days are fetched "
            "on top of this and consumed as warm-up before the window starts."
        ),
    )
    parser.add_argument("--markets", nargs="*", default=None, help="Specific KRW-* markets to test; defaults to all.")
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=config.INITIAL_CASH_KRW,
        help=(
            "Starting cash in KRW. New entries/averaging rounds are naturally "
            "skipped once cash runs out. Use a huge number to simulate "
            "unlimited capital."
        ),
    )
    args = parser.parse_args()

    if args.days < 1:
        parser.error("--days must be at least 1")

    # The first HIGH_LOOKBACK_DAYS bars of fetched history are warm-up: they
    # feed the 364-day rolling high and friends, and start_date is placed just
    # after them. `--days` previously set the FETCH count, so the actual window
    # came out as days - HIGH_LOOKBACK_DAYS: `--days 365` produced a 1-day
    # backtest and `--days 500` about 136 days. Fetch warm-up + window instead.
    fetch_count = args.days + config.HIGH_LOOKBACK_DAYS

    print("Fetching BTC reference data...", file=sys.stderr)
    btc_df = upbit_client.get_daily_candles("KRW-BTC", count=fetch_count)

    markets = args.markets or upbit_client.get_krw_markets()
    market_data = {}
    for market in markets:
        print(f"Fetching {market}...", file=sys.stderr)
        market_data[market] = upbit_client.get_daily_candles(market, count=fetch_count)

    if len(btc_df) <= config.HIGH_LOOKBACK_DAYS:
        print(
            f"Only {len(btc_df)} days of BTC history available, which is less than the "
            f"{config.HIGH_LOOKBACK_DAYS}-day warm-up. Nothing to backtest.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    start_date = btc_df.index[config.HIGH_LOOKBACK_DAYS]
    end_date = btc_df.index[-1]

    result = run_backtest(
        btc_df, market_data, start_date=start_date, end_date=end_date, initial_cash=args.initial_cash
    )

    window_days = len(btc_df) - config.HIGH_LOOKBACK_DAYS
    print(f"\nBacktest period: {start_date.date()} to {end_date.date()} ({window_days} days)")
    print(f"Warm-up history: {config.HIGH_LOOKBACK_DAYS} days before {start_date.date()}")
    print(f"Markets tested: {len(markets)}")
    print(f"Initial cash: {args.initial_cash:,.0f} KRW (position size: {config.POSITION_SIZE_KRW:,.0f} KRW/buy)")
    print(f"Final cash: {result['final_cash']:,.0f} KRW")
    print(f"Total actions: {len(result['actions'])}")
    print("Metrics:")
    for key, value in result["metrics"].items():
        print(f"  {key}: {value}")

    if result["open_detail"]:
        print(f"\nOpen positions ({len(result['open_detail'])}):")
        for d in result["open_detail"]:
            cur = f"{d['current_price']:,.1f}" if d["current_price"] is not None else "N/A"
            upnl = f"{d['unrealized_pnl']:,.0f}" if d["unrealized_pnl"] is not None else "N/A"
            print(
                f"  {d['market']:10s} rounds_used={d['rounds_used']} "
                f"entry={d['entry_price']:,.1f} avg={d['avg_price']:,.1f} cur={cur} "
                f"cost_basis={d['cost_basis']:,.0f} unrealized_pnl={upnl}"
            )


if __name__ == "__main__":
    main()
