from strategy_engine import exit_signal


def test_is_take_profit_true_at_threshold():
    assert exit_signal.is_take_profit(avg_price=1000, current_price=1050) is True


def test_is_take_profit_true_above_threshold():
    assert exit_signal.is_take_profit(avg_price=1000, current_price=1200) is True


def test_is_take_profit_false_below_threshold():
    assert exit_signal.is_take_profit(avg_price=1000, current_price=1049) is False
