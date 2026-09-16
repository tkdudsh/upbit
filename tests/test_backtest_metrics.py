import pytest
from strategy_engine.portfolio import ClosedTrade
from strategy_engine.backtest.metrics import compute_metrics


def test_compute_metrics_empty():
    result = compute_metrics([])
    assert result == {"num_trades": 0, "total_pnl": 0.0, "win_rate": 0.0, "total_return_pct": 0.0}


def test_compute_metrics_mixed_trades():
    trades = [
        ClosedTrade(market="KRW-ETH", avg_price=1000, exit_price=1050, qty=100, entry_date="d0", exit_date="d1"),
        ClosedTrade(market="KRW-XRP", avg_price=500, exit_price=450, qty=200, entry_date="d0", exit_date="d1"),
    ]
    # trade 1 pnl = (1050-1000)*100 = 5000, invested 100000
    # trade 2 pnl = (450-500)*200 = -10000, invested 100000
    result = compute_metrics(trades)

    assert result["num_trades"] == 2
    assert result["total_pnl"] == pytest.approx(-5000)
    assert result["win_rate"] == pytest.approx(0.5)
    assert result["total_return_pct"] == pytest.approx(-5000 / 200000)
