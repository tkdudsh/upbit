# strategy_engine/config.py
"""All tunable strategy thresholds. v1 defaults — tune via backtest."""

# --- Entry filter ---
HIGH_LOOKBACK_DAYS = 364              # "52-week" high/low, altcoins trade every day
RECENT_PUMP_LOOKBACK_DAYS = 14
RECENT_PUMP_RETURN_THRESHOLD = 0.30    # exclude if +30% or more over the lookback
NEAR_HIGH_THRESHOLD = 0.05             # exclude if within 5% of the 364-day high
DEEP_PULLBACK_THRESHOLD = 0.20         # confirm if 20%+ below the 364-day high
MA_SUPPORT_PERIODS = (120, 200)
MA_SUPPORT_BAND = 0.05                 # confirm if within 5% of either MA
RSI_PERIOD = 14
RSI_OVERSOLD = 30
VOLUME_RECOVERY_SHORT_PERIOD = 5
VOLUME_RECOVERY_LONG_PERIOD = 20
VOLUME_RECOVERY_RATIO = 1.5            # confirm if 5-day avg volume >= 1.5x 20-day avg
BB_PERIOD = 20
BB_STD = 2.0
BB_SQUEEZE_LOOKBACK_DAYS = 60
BB_SQUEEZE_TOLERANCE = 0.10            # "near the 60-day min" = within 10% of it

# --- Regime (downtrend) detection ---
REGIME_MA_PERIOD = 60
REGIME_SLOPE_LOOKBACK_DAYS = 5

# --- Averaging-down gates ---
AVERAGING_STEP_PCT = 0.10
MAX_AVERAGING_ROUNDS = 3
SUPPORT_LOOKBACK_DAYS = 60
SUPPORT_SURVIVAL_BAND = 0.03           # allowed if price hasn't broken more than 3% below the 60-day low
CAPITULATION_VOLUME_LOOKBACK_DAYS = 20
CAPITULATION_VOLUME_MULTIPLIER = 2.0   # a down day with 2x+ avg volume blocks averaging

# --- Exit ---
TAKE_PROFIT_PCT = 0.05

# --- Trading costs ---
# ASSUMPTION, VERIFY against Upbit's current fee schedule before trusting any
# backtest P&L: Upbit's KRW spot taker fee is approximately 0.05% per side.
# Applied to both the buy and the sell leg in ClosedTrade.pnl, so a round trip
# costs roughly 0.1% — material against a +5% take-profit target. Slippage is
# not modelled separately; widen this constant to approximate it.
FEE_RATE = 0.0005

# --- Backtest position sizing (percentage-based strategy, so this only scales
# reported KRW P&L, not returns) ---
POSITION_SIZE_KRW = 100_000
