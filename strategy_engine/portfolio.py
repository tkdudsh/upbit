from dataclasses import dataclass, field


@dataclass
class Position:
    market: str
    entries: list = field(default_factory=list)

    @property
    def rounds_used(self) -> int:
        return len(self.entries) - 1

    @property
    def total_qty(self) -> float:
        return sum(e["qty"] for e in self.entries)

    @property
    def avg_price(self) -> float:
        total_cost = sum(e["price"] * e["qty"] for e in self.entries)
        return total_cost / self.total_qty


@dataclass
class ClosedTrade:
    market: str
    avg_price: float
    exit_price: float
    qty: float
    entry_date: object
    exit_date: object

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.avg_price) * self.qty


class Portfolio:
    def __init__(self, position_size_krw: float):
        self.position_size_krw = position_size_krw
        self.positions: dict[str, Position] = {}
        self.closed_trades: list[ClosedTrade] = []

    def is_held(self, market: str) -> bool:
        return market in self.positions

    def open_position(self, market: str, price: float, trade_date) -> None:
        qty = self.position_size_krw / price
        self.positions[market] = Position(market=market, entries=[{"date": trade_date, "price": price, "qty": qty}])

    def add_to_position(self, market: str, price: float, trade_date) -> None:
        qty = self.position_size_krw / price
        self.positions[market].entries.append({"date": trade_date, "price": price, "qty": qty})

    def close_position(self, market: str, price: float, trade_date) -> ClosedTrade:
        position = self.positions.pop(market)
        trade = ClosedTrade(
            market=market,
            avg_price=position.avg_price,
            exit_price=price,
            qty=position.total_qty,
            entry_date=position.entries[0]["date"],
            exit_date=trade_date,
        )
        self.closed_trades.append(trade)
        return trade
