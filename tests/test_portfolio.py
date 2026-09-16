import pytest
from strategy_engine.portfolio import Portfolio


def test_open_position_sets_avg_price_and_qty():
    p = Portfolio(position_size_krw=100_000)
    p.open_position("KRW-ETH", price=1000, trade_date="2024-01-01")

    position = p.positions["KRW-ETH"]
    assert position.avg_price == pytest.approx(1000)
    assert position.total_qty == pytest.approx(100)
    assert position.rounds_used == 0
    assert p.is_held("KRW-ETH") is True
    assert p.is_held("KRW-XRP") is False


def test_add_to_position_updates_weighted_avg_price():
    p = Portfolio(position_size_krw=100_000)
    p.open_position("KRW-ETH", price=1000, trade_date="2024-01-01")
    p.add_to_position("KRW-ETH", price=900, trade_date="2024-01-02")

    position = p.positions["KRW-ETH"]
    # 100000 @1000 -> 100 qty; 100000 @900 -> 111.111 qty
    # avg = 200000 / 211.111 = 947.368...
    assert position.total_qty == pytest.approx(211.111, abs=0.01)
    assert position.avg_price == pytest.approx(947.368, abs=0.01)
    assert position.rounds_used == 1


def test_entry_price_is_the_first_entry_and_never_recomputed():
    p = Portfolio(position_size_krw=100_000)
    p.open_position("KRW-ETH", price=1000, trade_date="2024-01-01")
    position = p.positions["KRW-ETH"]

    assert position.entry_price == pytest.approx(1000)
    assert position.avg_price == pytest.approx(1000)

    p.add_to_position("KRW-ETH", price=900, trade_date="2024-01-02")

    # avg_price moves down with the added round; entry_price must not.
    assert position.avg_price == pytest.approx(947.368, abs=0.01)
    assert position.entry_price == pytest.approx(1000)

    p.add_to_position("KRW-ETH", price=800, trade_date="2024-01-03")
    assert position.entry_price == pytest.approx(1000)
    assert position.avg_price < 947.0


def test_close_position_records_closed_trade_and_removes_position():
    p = Portfolio(position_size_krw=100_000)
    p.open_position("KRW-ETH", price=1000, trade_date="2024-01-01")
    p.add_to_position("KRW-ETH", price=900, trade_date="2024-01-02")

    trade = p.close_position("KRW-ETH", price=1000, trade_date="2024-01-10")

    assert p.is_held("KRW-ETH") is False
    assert trade in p.closed_trades
    assert trade.pnl == pytest.approx(11111.11, abs=0.5)
