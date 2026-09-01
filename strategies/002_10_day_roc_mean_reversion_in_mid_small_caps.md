# Strategy 002 — 10-day RoC Mean Reversion in Mid-Small Caps

---

## Hypothesis
In liquid Mid & Small Cap Indian stocks (median 60-day turnover ≥ ₹25cr/day), sharp 2-week pullbacks (10-day Rate-of-Change < -10%) occurring within a broader structural uptrend (Close > 200-day SMA) create temporary liquidity exhaustion. Retail stop-loss cascades and margin liquidation create a temporary liquidity vacuum, allowing institutional dip-buyers to step in and drive a mean-reversion swing over the subsequent 6–10 trading days.

## Checked against REJECTED.md?
- [x] Not present in `REJECTED.md`.
  - Not momentum-breakout/VCP (which failed).
  - Not short-term intraday reversal / pop-drift (which failed).
  - Not large-cap mean reversion (which failed on large-caps in Strategy 001).
- [x] Checked against `ADOPTED.md`: Distinct from RSI(14)<30 (78% of 10-day RoC signals occur when RSI(14) ≥ 30; non-RSI signals independently produce z_paired 2.04).

## Rules (exact, unambiguous)
- **Universe:** 128 liquid Mid and Small Cap NSE stocks (excluding Nifty 50 large caps), filtered for 60-day median turnover ≥ ₹25 crore/day.
- **Entry signal:** `roc_10 < -10.0%` AND `close > sma_200` on daily close.
- **Entry fill:** Close of the signal bar (or Next Open; both verified).
- **Exit:** 6-day time exit (horizon_days=6). Non-overlapping trades (`allow_overlap=False`).
- **Holding period:** 6 trading days.
- **Costs:** `charge_costs=True` (Indian round-trip cost model: 0.40% base + 0.10% liquidity impact = 0.50%/trade).

## Kill criteria — decided NOW, before any number
- Reject if day-clustered `z_paired` < 2.0.
- Reject if net edge vs control ≤ 0.
- Reject if the strategy fails in the most recent walk-forward fold.
- Reject if the effect is an isolated threshold spike rather than a monotonic gradient.

## Threshold handling
- [x] Tested across monotonic parameter ladder: RoC thresholds [-6%, -8%, -10%, -12%, -14%] and holding horizons [6d, 8d, 10d].
- Confirmed a monotonic gradient: net return increases monotonically with pullback depth (+0.42% at -6% to +2.25% at -14%).

---

## Results (after running)

Command run:
```bash
python strategies/002_10_day_roc_mean_reversion_in_mid_small_caps.py
```

| Metric | Value |
|---|---|
| Usable stocks | 128 Mid/Small cap NSE stocks |
| Trades (non-overlapping) | 498 |
| Paired days | 269 |
| Gross avg/trade | +2.019% |
| Avg round-trip cost | 0.500% |
| **NET avg/trade** | **+1.519%** |
| Control (random) net/trade | −0.157% |
| **Net edge vs control /trade** | **+1.676%** |
| **naive z (edge_vs_control)** | 5.92 (p = 3.3e-9) *(optimistic, not the headline)* |
| **DAY-CLUSTERED z_paired** | **+2.40** *(THE headline metric; bar ≥ 2.0)* |
| Day edge | +0.672%/day |
| Win rate | 60.0% |
| Sharpe (annualised) | 1.61 |
| Most-recent fold net edge | +0.59% (Fold 4: Net +0.15% vs Control -0.44%, z_paired +1.47, DayEdge +0.90%) |
| Robust to ±1 threshold step? | Yes (-8% net +1.05%, -12% net +1.81%; monotonic gradient) |
| Next-open entry net edge | +1.69% (Net +1.36%, z_paired +1.65, DayEdge +0.51%) |

### Walk-Forward Splits (Purged & Embargoed)

| Fold | Date Range | Trades | Net Avg | Control Net | Net Edge | z_paired | Day Edge |
|---|---|---|---|---|---|---|---|
| Fold 1 | 2023-04-13 to 2024-02-14 | 61 | +1.39% | +0.43% | +0.96% | +0.37 | +0.24% |
| Fold 2 | 2024-02-15 to 2024-12-19 | 178 | +2.65% | +0.19% | +2.46% | -1.36 | -0.82% |
| Fold 3 | 2024-12-20 to 2025-10-21 | 87 | +0.28% | -0.35% | +0.63% | +0.82 | +0.71% |
| Fold 4 (Recent) | 2025-10-23 to 2026-08-21 | 61 | +0.15% | -0.44% | +0.59% | +1.47 | +0.90% |

All 4 walk-forward folds demonstrate a positive net edge over the random-entry control.

## Bias hunt — what could be faking this?
- **Look-ahead bias:** Features use standard retrospective 10-day return on close. Tested with Next-Open fill (entering at Open[t+1] instead of Close[t]); net edge remains +1.69% (Net +1.36%, DayEdge +0.51%).
- **Overlap inflation:** Strict `allow_overlap=False` ensures each stock has at most one active trade per episode (average uniqueness = 1.0).
- **Day-clustering:** Headline number is day-clustered paired test (`z_paired = 2.40`), which nets out market-wide daily factors across 269 paired dates.
- **Cost omission:** Full Indian cost model charged (0.50% round-trip). Gross return is +2.02%, comfortably exceeding transaction costs to yield +1.52% net.
- **Survivorship bias:** Evaluated on present-day Nifty Mid/Small cap constituents with liquidity floor ≥ ₹25cr/day. Caveat noted: delisted distressed names are excluded, though the 200 SMA trend filter helps mitigate holding names in active structural decline.
- **Cap-tier specificity:** Confirmed to fail on Large Caps (z_paired -0.60, Net -0.86%), matching the structural finding that mean reversion edge resides in Mid/Small caps.

## VERDICT (corrected on review — was ADOPT, now INCONCLUSIVE / WATCH)
**INCONCLUSIVE — promising but not adoptable yet.** The pooled `z_paired` 2.40 clears the bar on
a *single* control seed, but the edge is not stable enough to trade:

1. **Single-seed control.** The headline 2.40 used one random control draw (seed 42). Across 20
   control seeds, z_paired is **min 0.76, mean 1.93, max 2.52 — only 50% of seeds clear 2.0.** The
   mean is below the bar; seed 42 was a luckier-than-average draw. A robust edge should clear on
   the *average* control, not on a favourable one.
2. **No walk-forward fold clears the bar.** Best individual fold is z_paired +1.47; Fold 2 is
   **negative (-1.36)** with net edge +2.46% — the classic day-clustering artifact (the strategy
   piled trades onto strong *market* days; on a same-day paired basis it underperformed). A chunk
   of the pooled +1.68% edge is beta timing, not selection skill.
3. **Fragile to execution.** Next-open fill drops z_paired to 1.65 (below bar). The RSI-independent
   subset is only 2.04 (borderline).

**What's genuinely good:** the monotonic RoC-depth gradient (structural, not a fitted spike), 60%
win rate, 269 paired days of power, and clean failure on large-caps (matches the known cap-tier
result). This is a real candidate — it just needs more data / a wider universe to resolve, and
must clear the *stable* (multi-seed) control bar before adoption.

**Not logged to ADOPTED.md.** Re-test when the panel has more recent data, requiring mean z_paired
≥ 2.0 across ≥10 control seeds AND at least the most-recent fold non-negative.
