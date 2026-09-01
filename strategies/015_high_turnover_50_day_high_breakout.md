# Strategy 015 — High Turnover 50-Day High Breakout

Copy this to `strategies/NNN-shortname.md` and fill it in as you go. The top half is written
BEFORE you run anything (it's also your pre-run checklist); the bottom half after.

---

## Hypothesis
_One sentence: what inefficiency is this supposed to exploit, and why would it exist?_
_(If you can't name a reason the edge should exist, that's a red flag — say so.)_

## Checked against REJECTED.md?
- [ ] Not present, not a trivial variant of a rejected idea. (If it is → stop here.)

## Rules (exact, unambiguous)
- **Universe:** _(e.g. Nifty 500 NSE, liquid ≥₹25cr/day; state survivorship handling)_
- **Entry signal:** _(exact condition, on which bar it's KNOWN)_
- **Entry fill:** _(indicator signal → same close is fine; EVENT/news signal → NEXT open, mandatory)_
- **Exit:** _(stop, target, time horizon, and/or indicator exit filled at next open)_
- **Holding period:** _(bars)_
- **Costs:** charge_costs=True (always)

## Kill criteria — decided NOW, before any number
_What result makes this a REJECT? Commit to it before running._
- Reject if z_paired < 2.0, OR net edge ≤ 0, OR it dies in the most recent walk-forward fold.
- _(add any strategy-specific kill condition)_

## Threshold handling
- [ ] Threshold is pre-committed from theory (no search penalty), OR
- [ ] I scanned thresholds → will run block_bootstrap_pvalue + deflated_sharpe(effective_trials)
      and confirm a plateau/monotonic region, not a spike.

---

## Results (after running)

Command(s) run:
```
python <your_test_script>.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | |
| Paired days | |
| Net edge vs control /trade | |
| **naive z (edge_vs_control)** | _(optimistic, not the headline)_ |
| **DAY-CLUSTERED z_paired (single draw)** | _(one seed — not sufficient alone)_ |
| **MEAN z_paired across ≥20 control seeds** | **_(THE number — stable_day_clustered_z; bar is on the mean)_** |
| Pass rate (seeds with z_paired ≥ 2.0) | _(should be near 100%, not ~50%)_ |
| Per-fold z_paired (all folds) | _(not net-edge sign — the paired z)_ |
| Next-open z_paired | _(if it dies here, edge is execution-fragile)_ |
| Most-recent fold net edge | |
| Robust to ±1 threshold step? | |
| Search-deflated? (if scanned) | |

## Bias hunt — what could be faking this?
_Explicitly rule out each: look-ahead, overlap, day-clustering, survivorship, cost omission,
threshold fit, single-period luck. Which did you check and how?_

## VERDICT
**ADOPT / REJECT / INCONCLUSIVE-UNDERPOWERED** — _(one line, with z_paired and net edge)_

If REJECT → added a row to `REJECTED.md`? [ ]
