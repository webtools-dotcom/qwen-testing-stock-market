# Strategy 004 — Gap-Down Intraday Reversal in Structural Uptrend

---

## Hypothesis
In liquid Indian equities (turnover ≥ ₹25cr/day), when an overnight sentiment shock causes a stock
in an established long-term uptrend (Close > SMA 200) to open with a significant gap-down (Open ≤ Close[1] * 0.985),
intraday institutional absorption that drives the close above the open and into the upper portion of the
daily range ((Close - Low) / (High - Low) ≥ 0.60) signals liquidity exhaustion of panicked retail sellers,
creating a 6-10 day mean-reversion swing opportunity.

## Checked against REJECTED.md?
- [x] Not present in REJECTED.md. Distinct from single-day pop chasing, RSI<30, and event-driven news trading.

## Rules (exact, unambiguous)
- **Universe:** 88 Liquid NSE Equities (turnover ≥ ₹25cr/day, 5-year daily panel).
- **Entry signal:** `Open <= Close[1] * 0.985` (gap down ≥ 1.5%), `Close > Open` and `(Close - Low) / (High - Low) >= 0.60` (intraday green absorption closing in top 40% of range), `Close > SMA 200`, and `Turnover 60d >= 25cr`.
- **Entry fill:** Same close (indicator signal computed at EOD, standard MOC/next-open equivalent).
- **Exit:** Fixed 7-day holding horizon with stop-loss at 2.0 × ATR(14) (or open gap-through) and target at 2.0 × ATR(14).
- **Holding period:** 7 bars (swing horizon).
- **Costs:** `charge_costs=True` (Indian round-trip cost model: 0.40% baseline + liquidity impact).

## Kill criteria — decided NOW, before any number
- Reject if mean `z_paired` < 2.0 across ≥20 control seeds.
- Reject if net edge ≤ 0.
- Reject if the strategy collapses under day-clustering (naive z high, paired z low).
- Reject if it dies in the most recent walk-forward fold or fails to show positive paired z in out-of-sample splits.

## Threshold handling
- [x] Pre-committed baseline: Gap ≥ 1.5%, Bar position ≥ 0.60, 7-day hold.
- [x] Scanned 9-point grid (Gap 1.0/1.5/2.0%, Pos 0.50/0.60/0.70) with DSR and effective trials.

---

## Results (after running)

Command(s) run:
```bash
python strategies/004_gap_down_intraday_reversal_in_uptrend.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 444 |
| Paired days | 163 |
| Gross avg/trade | +1.189% |
| Avg round-trip cost | 0.500% |
| NET avg/trade | +0.689% |
| Control (random) avg | -0.202% |
| Net edge vs control /trade | +0.890% |
| **naive z (edge_vs_control)** | **3.93** (p = 8.54e-05) _(optimistic, completely deceptive)_ |
| **DAY-CLUSTERED z_paired (single draw)** | **0.09** (163 paired days, day_edge +0.026%) |
| **MEAN z_paired across ≥20 control seeds** | **0.81** (min: 0.08, max: 1.56) |
| **Pass rate (seeds with z_paired ≥ 2.0)** | **0.0%** (0 of 20 seeds cleared 2.0) |
| Per-fold z_paired (4 purged folds) | Fold 1: -0.12, Fold 2: -0.81, Fold 3: +0.53, Fold 4: +0.88 |
| Most-recent fold net edge | +2.35% (Fold 4), but z_paired only +0.88 (market beta) |
| Parameter grid z_paired range | -1.05 to +1.75 across all 9 combinations (none clears 2.0) |
| Effective trials | 8.65 (from 9 combinations) |
| Deflated Sharpe (DSR) | 1.000 (Observed SR: 1.58 on naive returns) |

---

## Bias hunt — what could be faking this?

1. **Day-Clustering Bias (THE KILLER):**
   - Naive z is **3.93**, but day-clustered paired z is **0.09** (mean **0.81** across 20 seeds).
   - Why? Gap-down intraday reversals cluster heavily across multiple stocks on broad market panic days (e.g. global market gap-downs). On days when the market rebounds, virtually all stocks bounce.
   - The trade-level naive test attributed the market-wide bounce to the strategy's stock selection. When each day's strategy return is paired against the control return on the *exact same day*, the day-edge drops from +0.890% to a negligible +0.026%!
2. **Walk-Forward Folds:**
   - 0 out of 4 folds clear the z_paired ≥ 2.0 bar (Fold 1: -0.12, Fold 2: -0.81, Fold 3: +0.53, Fold 4: +0.88).
   - Folds 1 and 2 exhibit negative paired z-scores despite positive trade averages.
3. **Threshold Sensitivity:**
   - Testing 1.0%, 1.5%, and 2.0% gap cutoffs shows that even the most extreme 2.0% gap threshold achieves z_paired of only 1.75 (below 2.0 bar) while cutting trade count in half (223 trades).

---

## VERDICT
**REJECT** — `naive z = 3.93` completely collapses under day-clustering to `mean z_paired = 0.81` across 20 seeds (0% pass rate, single-seed paired z = 0.09, day edge +0.026%). The perceived trade-level edge is entirely market beta from day-clustered panic bounces, with 0/4 walk-forward folds clearing 2.0.

- Added to `REJECTED.md`: Yes
