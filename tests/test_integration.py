"""End-to-end engine tests with NO mocking.

Every signal function (entry / exit_signal / averaging / regime) and a real
Portfolio are exercised against a hand-built synthetic price path. This is the
only place the cross-module contract between engine.py and averaging.py is
checked for real — each module's own unit tests mock the other side away, which
is exactly how the averaging ladder came to be measured against a moving
target (see C3 in the final review).
"""
import pandas as pd
import pytest

from strategy_engine import config, engine
from strategy_engine.portfolio import Portfolio

WARMUP_DAYS = 400
ENTRY_DAY_IDX = WARMUP_DAYS - 1  # last warm-up bar is the entry day
ENTRY_PRICE = 750.0
DECLINE_STEP = 0.98  # -2%/day: fine enough to cross each ladder rung cleanly,
                     # and shallow enough that is_support_alive's 3% band holds
RECOVERY_STEP = 1.03


def _coin_prices() -> list[float]:
    """Flat 1000 -> flat 750 (a 25% pullback) -> slow decline -> recovery.

    The 1000 plateau sets the 364-day rolling high, so on the entry day the
    close sits 25% below it: is_deep_pullback true, is_near_high false and
    is_recent_pump false, which is exactly one confirmation and no exclusion.
    """
    prices = [1000.0] * 100 + [ENTRY_PRICE] * (WARMUP_DAYS - 100)
    price = ENTRY_PRICE
    for _ in range(20):
        price *= DECLINE_STEP
        prices.append(price)
    for _ in range(20):
        price *= RECOVERY_STEP
        prices.append(price)
    return prices


def _ohlcv(closes, volume=100.0) -> pd.DataFrame:
    index = pd.DatetimeIndex(
        pd.date_range("2023-01-01", periods=len(closes), freq="D"), name="date"
    )
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            # Constant volume keeps is_capitulation false (it needs a down day
            # with >=2x the 20-day average volume) without extra bookkeeping.
            "volume": [volume] * len(closes),
        },
        index=index,
    )


def _btc_df(n: int) -> pd.DataFrame:
    # Steadily rising BTC -> is_downtrend(btc) is false -> is_bear_market is
    # false regardless of the coin's own trend, so the bear-market gate never
    # closes the averaging ladder during the decline.
    return _ohlcv([10_000.0 + i * 10 for i in range(n)])


def _drive() -> dict:
    """Run real daily cycles from the entry day until the position closes."""
    closes = _coin_prices()
    coin_df = _ohlcv(closes)
    btc_df = _btc_df(len(closes))
    portfolio = Portfolio(position_size_krw=config.POSITION_SIZE_KRW)

    entry_fills, averaging_fills, take_profits = [], [], []
    avg_price_at_exit = None

    for i in range(ENTRY_DAY_IDX, len(closes)):
        trade_date = coin_df.index[i]
        held_before = portfolio.positions.get("KRW-ETH")
        avg_before = held_before.avg_price if held_before else None

        actions = engine.run_daily_cycle(
            portfolio,
            {"KRW-ETH": coin_df.iloc[: i + 1]},
            btc_df.iloc[: i + 1],
            trade_date=trade_date,
        )

        for action in actions:
            if action["type"] == "entry":
                entry_fills.append(closes[i])
            elif action["type"] == "averaging":
                averaging_fills.append(closes[i])
            elif action["type"] == "take_profit":
                take_profits.append(closes[i])
                avg_price_at_exit = avg_before

        if take_profits:
            break

    return {
        "entry_fills": entry_fills,
        "averaging_fills": averaging_fills,
        "take_profits": take_profits,
        "avg_price_at_exit": avg_price_at_exit,
        "portfolio": portfolio,
    }


def test_full_cycle_entry_three_averaging_rounds_then_take_profit():
    result = _drive()

    assert result["entry_fills"] == [pytest.approx(ENTRY_PRICE)]
    assert len(result["averaging_fills"]) == config.MAX_AVERAGING_ROUNDS
    assert len(result["take_profits"]) == 1


def test_averaging_ladder_steps_from_the_original_entry_price():
    result = _drive()
    fills = result["averaging_fills"]
    assert len(fills) == 3

    for round_number, fill_price in enumerate(fills, start=1):
        threshold = ENTRY_PRICE * (1 - config.AVERAGING_STEP_PCT * round_number)
        # Each round must fire on the FIRST bar at or below its rung measured
        # from the ORIGINAL entry price, i.e. within one -2% bar of the rung.
        # If the ladder were anchored to the recomputed weighted average, the
        # rungs would drift to roughly -10% / -24% / -39% and rounds 2 and 3
        # would land far below these bands.
        assert fill_price <= threshold, (
            f"round {round_number} fired at {fill_price:.2f}, "
            f"above its -{round_number * 10}% rung of {threshold:.2f}"
        )
        assert fill_price > threshold * DECLINE_STEP, (
            f"round {round_number} fired at {fill_price:.2f}, more than one bar "
            f"below its -{round_number * 10}% rung of {threshold:.2f} — the "
            f"ladder is drifting (anchored to a moving average price?)"
        )

    # The whole ladder stays inside the documented -30% envelope.
    assert fills[-1] > ENTRY_PRICE * (1 - 0.30) * DECLINE_STEP


def test_entry_price_and_avg_price_really_diverged_during_the_run():
    # Guards the test above from passing vacuously: if add_to_position did not
    # in fact move avg_price, anchoring to entry_price would be a no-op.
    result = _drive()
    avg_at_exit = result["avg_price_at_exit"]

    assert avg_at_exit < ENTRY_PRICE
    # 4 buys of 100k at the entry price and the three ladder rungs.
    expected_qty = sum(
        config.POSITION_SIZE_KRW / p for p in [ENTRY_PRICE] + result["averaging_fills"]
    )
    assert avg_at_exit == pytest.approx(
        (config.POSITION_SIZE_KRW * 4) / expected_qty, rel=1e-9
    )


def test_take_profit_uses_the_recomputed_average_not_the_entry_price():
    result = _drive()
    exit_price = result["take_profits"][0]
    avg_at_exit = result["avg_price_at_exit"]

    # +5% on the weighted average (spec: "+5% 익절: 평균매수가 대비") — and well
    # BELOW the original entry price, proving the two references are distinct.
    assert (exit_price - avg_at_exit) / avg_at_exit >= config.TAKE_PROFIT_PCT
    assert exit_price < ENTRY_PRICE

    trade = result["portfolio"].closed_trades[0]
    assert trade.market == "KRW-ETH"
    assert trade.avg_price == pytest.approx(avg_at_exit)
    assert result["portfolio"].is_held("KRW-ETH") is False
