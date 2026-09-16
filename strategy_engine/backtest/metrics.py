from strategy_engine.portfolio import ClosedTrade


def compute_metrics(closed_trades: list) -> dict:
    if not closed_trades:
        return {"num_trades": 0, "total_pnl": 0.0, "win_rate": 0.0, "total_return_pct": 0.0}

    total_pnl = sum(t.pnl for t in closed_trades)
    wins = sum(1 for t in closed_trades if t.pnl > 0)
    total_invested = sum(t.avg_price * t.qty for t in closed_trades)

    return {
        "num_trades": len(closed_trades),
        "total_pnl": total_pnl,
        "win_rate": wins / len(closed_trades),
        "total_return_pct": total_pnl / total_invested if total_invested else 0.0,
    }
