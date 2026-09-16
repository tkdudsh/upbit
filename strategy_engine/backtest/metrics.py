def compute_metrics(closed_trades: list, open_positions=(), current_prices=None) -> dict:
    """Performance summary over closed trades plus marked-to-market open ones.

    Take-profit is the only thing that closes a trade (there is no stop-loss by
    design), so every closed trade is a winner by construction: measured on
    closed trades alone, win_rate is always 1.0 and a losing position simply
    sits open forever, invisible. Open positions are therefore marked to market
    at `current_prices` so the output can actually show a loss — which is the
    whole point of a backtest used to tune config.py's thresholds.

    Positions with no entry in `current_prices` are skipped (neither their
    value nor their cost basis is counted).
    """
    current_prices = current_prices or {}

    realized_pnl = sum(t.pnl for t in closed_trades)
    wins = sum(1 for t in closed_trades if t.pnl > 0)
    realized_invested = sum(t.avg_price * t.qty for t in closed_trades)

    unrealized_pnl = 0.0
    open_invested = 0.0
    for position in open_positions:
        price = current_prices.get(position.market)
        if price is None:
            continue
        unrealized_pnl += (price - position.avg_price) * position.total_qty
        open_invested += position.avg_price * position.total_qty

    total_invested = realized_invested + open_invested
    total_pnl = realized_pnl + unrealized_pnl

    return {
        "num_trades": len(closed_trades),
        "num_open": len(open_positions),
        "realized_pnl": float(realized_pnl),
        "unrealized_pnl": float(unrealized_pnl),
        "total_pnl": float(total_pnl),
        "win_rate": (wins / len(closed_trades)) if closed_trades else 0.0,
        "total_return_pct": (total_pnl / total_invested) if total_invested else 0.0,
    }
