import pandas as pd
from unittest.mock import patch
from strategy_engine import entry


def _df(closes, volumes=None, highs=None, lows=None):
    n = len(closes)
    return pd.DataFrame({
        "close": closes,
        "high": highs or closes,
        "low": lows or closes,
        "volume": volumes or [100] * n,
    })


def test_is_recent_pump_true_when_return_exceeds_threshold():
    # flat history, then +50% in the last 14 days
    closes = [100] * 50 + [100 * (1.5 ** (i / 14)) for i in range(1, 15)]
    df = _df(closes)
    assert entry.is_recent_pump(df) is True


def test_is_recent_pump_false_when_flat():
    closes = [100] * 60
    df = _df(closes)
    assert entry.is_recent_pump(df) is False


def test_is_near_high_true_at_the_high():
    closes = list(range(1, 101))  # strictly increasing, last value is the max
    df = _df(closes)
    assert entry.is_near_high(df) is True


def test_is_near_high_false_when_far_below_high():
    closes = [100] + [50] * 99  # made a high of 100 long ago, now far below it
    df = _df(closes)
    assert entry.is_near_high(df) is False


def test_is_deep_pullback_true_after_big_drop_from_high():
    closes = [100] * 5 + [75] * 95  # 25% below the 364-day (or shorter, here 100-day) high
    df = _df(closes)
    assert entry.is_deep_pullback(df) is True


def test_is_deep_pullback_false_when_close_to_high():
    closes = [100] * 100
    df = _df(closes)
    assert entry.is_deep_pullback(df) is False


def test_is_near_ma_support_true_when_close_tracks_ma():
    closes = [100] * 250  # flat: close always equals every MA
    df = _df(closes)
    assert entry.is_near_ma_support(df) is True


def test_is_near_ma_support_false_when_far_above_ma():
    # steadily rising for 250 days puts the last close well above the 120/200 MA
    closes = [100 + i * 2 for i in range(250)]
    df = _df(closes)
    assert entry.is_near_ma_support(df) is False


def test_is_oversold_bounce_true_on_rsi_bounce_from_oversold():
    # decline pushes RSI under 30, then one up day bounces it
    closes = [100 - i for i in range(30)] + [72]
    df = _df(closes)
    assert entry.is_oversold_bounce(df) is True


def test_is_oversold_bounce_false_when_rsi_is_high():
    closes = [100 + i for i in range(31)]
    df = _df(closes)
    assert entry.is_oversold_bounce(df) is False


def test_is_volume_recovering_true_when_recent_volume_spikes():
    volumes = [100] * 40 + [200] * 5
    df = _df([100] * 45, volumes=volumes)
    assert entry.is_volume_recovering(df) is True


def test_is_volume_recovering_false_when_flat():
    df = _df([100] * 45, volumes=[100] * 45)
    assert entry.is_volume_recovering(df) is False


def test_is_volatility_squeeze_expanding_true_after_squeeze_then_expansion():
    # low, stable volatility for a while, then a sudden expansion on the last day
    stable = [100, 101, 100, 101, 100] * 16  # 80 rows of tight, low-volatility oscillation
    df = _df(stable + [130])  # one big jump expands the band sharply
    assert entry.is_volatility_squeeze_expanding(df) is True


def test_is_volatility_squeeze_expanding_false_when_volatility_stays_flat():
    stable = [100, 101, 100, 101, 100] * 17
    df = _df(stable)
    assert entry.is_volatility_squeeze_expanding(df) is False


def test_entry_allowed_composition_table():
    df = _df([100] * 10)  # content doesn't matter, predicates are mocked below
    base_patches = {
        "is_recent_pump": False,
        "is_near_high": False,
        "is_deep_pullback": False,
        "is_near_ma_support": False,
        "is_oversold_bounce": False,
        "is_volume_recovering": False,
        "is_volatility_squeeze_expanding": False,
    }

    def run_with(**overrides):
        values = {**base_patches, **overrides}
        with patch.multiple("strategy_engine.entry", **{k: lambda df, v=v: v for k, v in values.items()}):
            return entry.entry_allowed(df)

    # no exclusions, no confirmations -> not allowed
    assert run_with() is False
    # no exclusions, one confirmation -> allowed
    assert run_with(is_deep_pullback=True) is True
    assert run_with(is_near_ma_support=True) is True
    assert run_with(is_oversold_bounce=True) is True
    assert run_with(is_volume_recovering=True) is True
    assert run_with(is_volatility_squeeze_expanding=True) is True
    # exclusion present, even with a confirmation -> not allowed
    assert run_with(is_recent_pump=True, is_deep_pullback=True) is False
    assert run_with(is_near_high=True, is_deep_pullback=True) is False
