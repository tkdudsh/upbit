# upbit

업비트 매매프로그램

`strategy_engine/` is a signal-computation and backtest engine for Upbit
KRW-market altcoins. It computes entry / take-profit / averaging-down /
bear-market signals and replays them over historical daily candles. It does
**not** place orders — there is no live trading in this repo.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

## Running the tests

From the repo root:

```bash
python -m pytest        # or simply: pytest
```

`pyproject.toml` sets `pythonpath = ["."]` so bare `pytest` can import the
flat-layout `strategy_engine` package without installing it.

## Running a backtest against live Upbit data

```bash
python -m strategy_engine.scripts.run_backtest --markets KRW-ETH --days 730
```

- `--days` is the length of the **backtest window itself**. An additional
  `config.HIGH_LOOKBACK_DAYS` (364) days of history is fetched on top of it and
  consumed as indicator warm-up, so `--days 730` fetches 1094 daily candles.
- `--markets` is optional; omitting it backtests every KRW-* market except
  `KRW-BTC` (which is always fetched separately as the regime reference). That
  is several hundred markets and a few hundred paginated API calls.

Output reports realized P&L from closed (take-profit) trades plus open
positions marked to market at the last close in the window, so a losing run
actually shows a loss.

Every threshold lives in `strategy_engine/config.py`. The values there are v1
starting points, not validated — treat any backtest numbers as informational
until they have been tuned.
