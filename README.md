# backtesting-unique-strategies

A disciplined sandbox for discovering and **honestly** backtesting stock-market trading
strategies (primarily NSE/BSE). The point of this repo is not to find strategies that look good —
it's to kill the ones that only *look* good before they cost real money.

## For the AI assistant (Gemini or any model)
Read **`START_HERE.md`** first, every session. Then `METHODOLOGY.md` and `REJECTED.md`. Your job
is to try to break every strategy, not to confirm it — see START_HERE for why.

## For a human
```bash
pip install -r requirements.txt
python backtest_engine.py     # self-check the honest engine (offline)
python data_loader.py         # smoke-test data + features (needs network)
```

## Layout
```
AGENTS.md / GEMINI.md  # auto-loaded agent context — read first, every session
START_HERE.md          # session bootstrap for the AI — the prime directive + workflow
METHODOLOGY.md         # the 7 ways a backtest lies, and how to stop each one
REJECTED.md            # strategies already killed — never re-test these
ADOPTED.md             # strategies that survived — the baseline a new idea must beat
STRATEGY_TEMPLATE.md   # the per-strategy checklist (new_strategy.py copies it for you)
new_strategy.py        # `python new_strategy.py "<name>"` → scaffolds the next NNN .md + .py stub
backtest_engine.py     # the honest engine (day-clustered z_paired, costs, honest fills) — DON'T reinvent
data_loader.py         # yfinance panel + RSI/ATR features, cached (auto-invalidates on universe change)
ledger.py              # `ledger.py reject|adopt "<idea>" "<why>"` → auto-appends to the ledgers
strategies/            # 001_* is the worked example; one .py + .md per strategy tested
cache/                 # downloaded price panels (gitignored)
```

## The whole philosophy in three lines
1. Compare against a **random-entry control**, always. The edge is strategy − control.
2. The headline number is **day-clustered `z_paired`**, never the trade-level z. Bar: ≥ 2.0, net of costs.
3. If it looks clearly great, distrust it hardest — that's exactly when the sister project was wrong three times.
