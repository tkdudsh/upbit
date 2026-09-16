from . import config


def is_take_profit(avg_price: float, current_price: float, take_profit_pct: float = config.TAKE_PROFIT_PCT) -> bool:
    return (current_price - avg_price) / avg_price >= take_profit_pct
