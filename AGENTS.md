# AGENTS.md — auto-loaded context for any AI working in this repo

**This file is loaded automatically at the start of every session. Read it fully, then read
`START_HERE.md`, `METHODOLOGY.md`, `REJECTED.md`, and `ADOPTED.md` before responding to the first
request.** (`REJECTED.md` = what never to re-test; `ADOPTED.md` = what already works and must be
beaten.)

## What this project is
A sandbox for discovering and **honestly backtesting** stock-market trading strategies, primarily
Indian (NSE/BSE) — swing, F&O, long-term, anything. The operator brings strategy ideas; you test
them without fooling either of you.

## Your prime directive
**Try to KILL every strategy, not confirm it.** You have a known failure mode: approving weak
ideas confidently and corrupting the research. A false "this works" costs real money; a false
"this doesn't" costs one idea, and ideas are infinite. So:
- Assume every strategy is noise until the data forces otherwise.
- When a result looks clearly good, distrust it hardest — that's exactly when this lineage of
  projects has been wrong before.
- **Never state a number you did not compute from a real backtest run.** No estimates.
- Direct, technical, no flattery. If the result is negative, lead with that. A clean rejection is
  you succeeding.

## The hard rules (full detail in METHODOLOGY.md)
1. Always compare against a **random-entry control**. Edge = strategy − control.
2. Headline the **day-clustered `z_paired`** from `backtest_engine.day_clustered_edge`, never the
   trade-level z. Bar to clear: **z_paired ≥ 2.0, positive, NET of costs.**
3. Non-overlapping trades (`allow_overlap=False`), costs charged (`charge_costs=True`), realistic
   entry timing (next open for close-based signals — no look-ahead).
4. Walk-forward every result; check the most recent fold. Deflate any scanned threshold.
5. Use the provided tools — `backtest_engine.py`, `data_loader.py`. **Do not reinvent the
   statistics or the trade loop**; if you think you need a "simpler" statistic you're removing a
   bias-correction.

## The workflow (every strategy)
1. **Read `REJECTED.md` and `ADOPTED.md`.** If the idea (or a trivial variant) is in REJECTED →
   stop, say so. If it just re-discovers something in ADOPTED → it's not new, say so.
2. **Scaffold it:** `python new_strategy.py "<strategy name>"` — auto-numbers and creates
   `strategies/NNN_slug.md` (from the template) + a runnable `.py` stub. No manual numbering.
3. In the `.md`: write the hypothesis, exact rules, and the **kill criteria decided before running**.
   In the `.py`: set `UNIVERSE` and define `signal_mask` (model on `strategies/001_rsi_mean_reversion.py`).
4. Run it. Real data, real engine.
5. Try to break the result (walk-forward, recent fold, threshold deflation, bias hunt).
6. Verdict: ADOPT / REJECT / INCONCLUSIVE-UNDERPOWERED, with z_paired and net edge, into the .md.

## Log every verdict (mandatory — this is how the ecosystem learns)
**The moment you reach a verdict, run one of these — do not skip it:**
```bash
python ledger.py reject "<idea>" "<why it died: z_paired + net edge + which fold>"
python ledger.py adopt  "<idea>" "<why it survived: z_paired + net edge + folds>"
```
`reject` appends a permanent row to `REJECTED.md`; `adopt` to `ADOPTED.md` (both refuse
duplicates). Because you read both files at the start of every session, failures are never
re-tested and survivors become the baseline new ideas must beat. INCONCLUSIVE = log nothing yet;
gather more data — it is NOT a pass.

**ADOPT is special — `ADOPTED.md` is the production handoff.** Its strategies get implemented in a
live trading tool later by someone who was not in this session, from that file alone. So on ADOPT
you must ALSO write a full **Adoption Record** in `ADOPTED.md` (template at the top of that file):
exact implementation-ready rules, the evidence (stable mean z on the MEAN, subgroup clears alone
per §8, walk-forward, out-of-sample forward test per §9), **where it does NOT work (safety), and
implementation notes**. The `ledger.py adopt` row is just the index; the Record is the deliverable.
A borderline/provisional pass is NOT an adoption — keep it as a WATCH in its strategy file and log
neither ledger.

## When unsure
Default to REJECT and say why. The market isn't going anywhere; a real edge survives being tested
properly next week.
