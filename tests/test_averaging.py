import pandas as pd
from unittest.mock import patch
from strategy_engine import averaging


def _df(closes, volumes=None):
    n = len(closes)
    return pd.DataFrame({"close": closes, "volume": volumes or [100] * n})


def test_has_reached_step_true_at_first_averaging_round():
    # avg 1000, current 899 -> -10.1%, rounds_used=0 -> first averaging round threshold is -10%
    assert averaging.has_reached_step(avg_price=1000, current_price=899, rounds_used=0) is True


def test_has_reached_step_false_before_threshold():
    assert averaging.has_reached_step(avg_price=1000, current_price=910, rounds_used=0) is False


def test_has_reached_step_requires_next_step_for_second_round():
    # after 1 round used, need -20% from original avg, not just -10%
    assert averaging.has_reached_step(avg_price=1000, current_price=850, rounds_used=1) is False
    assert averaging.has_reached_step(avg_price=1000, current_price=799, rounds_used=1) is True


def test_has_reached_step_false_when_rounds_exhausted():
    # MAX_AVERAGING_ROUNDS = 3, rounds_used=3 means no more rounds allowed
    assert averaging.has_reached_step(avg_price=1000, current_price=100, rounds_used=3) is False


def test_is_support_alive_true_when_within_band_of_recent_low():
    closes = [100, 90, 80, 82, 81]  # recent low 80, current 81 (within 3%)
    df = _df(closes)
    assert averaging.is_support_alive(df) is True


def test_is_support_alive_false_when_broken_below_band():
    closes = [100, 90, 80, 82, 70]  # current 70 is far below the recent low of 80
    df = _df(closes)
    assert averaging.is_support_alive(df) is False


def test_is_capitulation_true_on_down_day_with_volume_spike():
    closes = [100] * 20 + [90]  # down day
    volumes = [100] * 20 + [250]  # 2.5x the 20-day average
    df = _df(closes, volumes)
    assert averaging.is_capitulation(df) is True


def test_is_capitulation_false_on_down_day_with_normal_volume():
    closes = [100] * 20 + [90]
    volumes = [100] * 21
    df = _df(closes, volumes)
    assert averaging.is_capitulation(df) is False


def test_is_capitulation_false_on_up_day_even_with_volume_spike():
    closes = [100] * 20 + [110]
    volumes = [100] * 20 + [250]
    df = _df(closes, volumes)
    assert averaging.is_capitulation(df) is False


def test_averaging_allowed_composition_table():
    coin_df = _df([100] * 10)
    btc_df = _df([100] * 10)

    def run_with(reached=True, support=True, capitulation=False, bear=False):
        with patch("strategy_engine.averaging.has_reached_step", return_value=reached), \
             patch("strategy_engine.averaging.is_support_alive", return_value=support), \
             patch("strategy_engine.averaging.is_capitulation", return_value=capitulation), \
             patch("strategy_engine.regime.is_bear_market", return_value=bear):
            return averaging.averaging_allowed(coin_df, btc_df, avg_price=1000, current_price=900, rounds_used=0)

    assert run_with() is True
    assert run_with(reached=False) is False
    assert run_with(support=False) is False
    assert run_with(capitulation=True) is False
    assert run_with(bear=True) is False
