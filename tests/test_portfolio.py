import pytest
from strategy_engine import config
from strategy_engine.portfolio import ClosedTrade, Portfolio


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
    # qty = 100 + 1000/9 = 211.1111..., avg = 200000/211.1111 = 947.3684...
    # gross = 1000 * 211.1111 - 200000                        = 11111.111
    # fees  = (200000 + 211111.111) * 0.0005                  =   205.556
    # net                                                     = 10905.556
    assert trade.pnl == pytest.approx(10905.556, abs=0.01)


def test_pnl_nets_out_round_trip_fees():
    trade = ClosedTrade(
        market="KRW-ETH", avg_price=1000, exit_price=1050, qty=100,
        entry_date="d0", exit_date="d1",
    )
    # gross = (1050-1000)*100 = 5000
    # fees  = (1000*100 + 1050*100) * 0.0005 = 205000 * 0.0005 = 102.5
    assert trade.pnl == pytest.approx(5000 - 102.5)
    assert config.FEE_RATE == 0.0005


def test_pnl_can_be_negative_purely_from_fees():
    # Flat round trip: no price move, but the fees still cost money.
    trade = ClosedTrade(
        market="KRW-ETH", avg_price=1000, exit_price=1000, qty=100,
        entry_date="d0", exit_date="d1",
    )
    assert trade.pnl == pytest.approx(-(200000 * 0.0005))


def test_cash_is_unconstrained_by_default():
    p = Portfolio(position_size_krw=15_000)
    assert p.cash == float("inf")
    assert p.can_afford() is True
    for i in range(50):
        p.open_position(f"KRW-COIN{i}", price=1000, trade_date="2024-01-01")
    assert p.can_afford() is True


def test_cash_decreases_on_open_and_add_increases_on_close():
    p = Portfolio(position_size_krw=15_000, initial_cash=100_000)
    assert p.cash == 100_000

    p.open_position("KRW-ETH", price=1000, trade_date="2024-01-01")
    assert p.cash == pytest.approx(85_000)

    p.add_to_position("KRW-ETH", price=900, trade_date="2024-01-02")
    assert p.cash == pytest.approx(70_000)

    position = p.positions["KRW-ETH"]
    total_qty = position.total_qty
    p.close_position("KRW-ETH", price=1000, trade_date="2024-01-10")
    assert p.cash == pytest.approx(70_000 + 1000 * total_qty)


def test_can_afford_false_once_cash_runs_out():
    p = Portfolio(position_size_krw=15_000, initial_cash=20_000)
    assert p.can_afford() is True

    p.open_position("KRW-ETH", price=1000, trade_date="2024-01-01")
    assert p.cash == pytest.approx(5_000)
    assert p.can_afford() is False  # 5,000 < position_size_krw (15,000)
