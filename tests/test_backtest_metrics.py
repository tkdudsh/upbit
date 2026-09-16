import pytest
from strategy_engine.portfolio import ClosedTrade, Position
from strategy_engine.backtest.metrics import compute_metrics


def test_compute_metrics_empty():
    result = compute_metrics([])
    assert result == {
        "num_trades": 0,
        "num_open": 0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "total_return_pct": 0.0,
    }


def test_compute_metrics_mixed_trades():
    trades = [
        ClosedTrade(market="KRW-ETH", avg_price=1000, exit_price=1050, qty=100, entry_date="d0", exit_date="d1"),
        ClosedTrade(market="KRW-XRP", avg_price=500, exit_price=450, qty=200, entry_date="d0", exit_date="d1"),
    ]
    # trade 1 gross pnl = (1050-1000)*100 = 5000, invested 100000,
    #         fees = (1000*100 + 1050*100) * 0.0005 = 102.5 -> pnl 4897.5
    # trade 2 gross pnl = (450-500)*200 = -10000, invested 100000,
    #         fees = (500*200 + 450*200) * 0.0005 = 95.0 -> pnl -10095.0
    expected_pnl = 4897.5 + -10095.0
    result = compute_metrics(trades)

    assert result["num_trades"] == 2
    assert result["num_open"] == 0
    assert result["realized_pnl"] == pytest.approx(expected_pnl)
    assert result["unrealized_pnl"] == pytest.approx(0.0)
    assert result["total_pnl"] == pytest.approx(expected_pnl)
    assert result["win_rate"] == pytest.approx(0.5)
    assert result["total_return_pct"] == pytest.approx(expected_pnl / 200000)


def test_compute_metrics_marks_open_positions_to_market():
    trades = [
        ClosedTrade(market="KRW-ETH", avg_price=1000, exit_price=1050, qty=100, entry_date="d0", exit_date="d1"),
    ]
    realized = (1050 - 1000) * 100 - (1000 * 100 + 1050 * 100) * 0.0005  # 4897.5

    open_positions = [
        Position(market="KRW-XRP", entries=[{"date": "d0", "price": 500, "qty": 200}]),
    ]
    # underwater: marked at 400 -> (400-500)*200 = -20000, cost basis 100000
    result = compute_metrics(trades, open_positions, {"KRW-XRP": 400})

    assert result["num_trades"] == 1
    assert result["num_open"] == 1
    assert result["realized_pnl"] == pytest.approx(realized)
    assert result["unrealized_pnl"] == pytest.approx(-20000)
    assert result["total_pnl"] == pytest.approx(realized - 20000)
    # take-profit-only exits make win_rate structurally 1.0; the loss shows up
    # in total_pnl / total_return_pct instead.
    assert result["win_rate"] == pytest.approx(1.0)
    assert result["total_return_pct"] == pytest.approx((realized - 20000) / 200000)
    assert result["total_pnl"] < 0


def test_compute_metrics_skips_open_position_without_a_current_price():
    open_positions = [
        Position(market="KRW-XRP", entries=[{"date": "d0", "price": 500, "qty": 200}]),
        Position(market="KRW-DOGE", entries=[{"date": "d0", "price": 100, "qty": 1000}]),
    ]
    # KRW-DOGE has no quote -> neither its value nor its cost basis counts.
    result = compute_metrics([], open_positions, {"KRW-XRP": 550})

    assert result["num_open"] == 2
    assert result["unrealized_pnl"] == pytest.approx((550 - 500) * 200)
    assert result["total_pnl"] == pytest.approx(10000)
    assert result["total_return_pct"] == pytest.approx(10000 / 100000)


def test_compute_metrics_all_open_none_priced_is_all_zero():
    open_positions = [
        Position(market="KRW-XRP", entries=[{"date": "d0", "price": 500, "qty": 200}]),
    ]
    result = compute_metrics([], open_positions, {})

    assert result["unrealized_pnl"] == 0.0
    assert result["total_pnl"] == 0.0
    assert result["total_return_pct"] == 0.0
    assert result["win_rate"] == 0.0
