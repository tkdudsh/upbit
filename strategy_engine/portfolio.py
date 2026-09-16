from dataclasses import dataclass, field

from . import config


@dataclass
class Position:
    market: str
    entries: list = field(default_factory=list)

    @property
    def rounds_used(self) -> int:
        return len(self.entries) - 1

    @property
    def entry_price(self) -> float:
        """The original, first-round entry price — never recomputed.

        The averaging ladder measures its -10%/-20%/-30% steps against this
        fixed reference. Using avg_price there would measure each step against
        a target that add_to_position has already pulled down, so the ladder
        would drift to roughly -10%/-24%/-39%. Take-profit deliberately still
        uses avg_price (spec: "+5% 익절: 평균매수가 대비").
        """
        return self.entries[0]["price"]

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
        """Net P&L after round-trip exchange fees (buy leg + sell leg)."""
        gross = (self.exit_price - self.avg_price) * self.qty
        fees = (self.avg_price * self.qty + self.exit_price * self.qty) * config.FEE_RATE
        return gross - fees


class Portfolio:
    def __init__(self, position_size_krw: float, initial_cash: float | None = None):
        """`initial_cash=None` means unconstrained (unlimited capital) — the
        original backtest assumption. Pass a real number to make the engine
        naturally skip new entries/averaging rounds once cash runs out."""
        self.position_size_krw = position_size_krw
        self.cash = initial_cash if initial_cash is not None else float("inf")
        self.positions: dict[str, Position] = {}
        self.closed_trades: list[ClosedTrade] = []

    def is_held(self, market: str) -> bool:
        return market in self.positions

    def can_afford(self) -> bool:
        return self.cash >= self.position_size_krw

    def open_position(self, market: str, price: float, trade_date) -> None:
        qty = self.position_size_krw / price
        self.cash -= self.position_size_krw
        self.positions[market] = Position(market=market, entries=[{"date": trade_date, "price": price, "qty": qty}])

    def add_to_position(self, market: str, price: float, trade_date) -> None:
        qty = self.position_size_krw / price
        self.cash -= self.position_size_krw
        self.positions[market].entries.append({"date": trade_date, "price": price, "qty": qty})

    def close_position(self, market: str, price: float, trade_date) -> ClosedTrade:
        position = self.positions.pop(market)
        self.cash += price * position.total_qty
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
