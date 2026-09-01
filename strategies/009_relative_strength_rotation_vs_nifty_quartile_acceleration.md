# Strategy 009 — Relative Strength Rotation vs Nifty (Quartile Acceleration)

---

## Hypothesis
Stocks that rapidly transition from bottom-quartile relative performance (vs Nifty 50) to
top-quartile relative performance over a 20-day window are catching the inflection point of
institutional sector/thematic rotation. Indian markets exhibit persistent 2-6 week sectoral
rotation waves (PSU Banks → IT → Pharma → Auto etc.) driven by DII/FPI flow concentration.
A stock making this Q1→Q4 leap signals fresh institutional accumulation entering a name that
was recently a laggard, generating a 6-10 day continuation drift.

**Why the edge would exist:** Cross-sectional momentum is one of the most replicated anomalies
globally (Jegadeesh & Titman 1993, Rouwenhorst 1999 for emerging markets). The Q1→Q4 transition
captures the steepest part of the relative-strength curve — stocks being actively rotated into.
By measuring performance *relative* to the index, the signal is partially immunized against
market-beta day-clustering (the #1 killer in this project).

**Why it might be fake:** (1) The quartile transition may simply select stocks that had the
biggest recent gap-up — i.e. we're buying post-pop, which already died in REJECTED.md (big
single-day gainers: no post-pop drift). (2) Day-clustering: if the rotation happens sector-wide
on one day, many stocks trigger simultaneously and share forward returns. (3) The 20-day lookback
and quartile thresholds introduce two implicit parameters that could be fit to noise.

## Checked against REJECTED.md?
- [x] Not present, not a trivial variant. Cross-sectional RS rotation vs index is distinct from:
  - RSI mean reversion (different signal class — momentum, not mean reversion)
  - Momentum-breakout / VCP (REJECTED: uses absolute price patterns, not relative strength)
  - 52-week-high nearness (REJECTED: absolute high, not relative performance acceleration)
  - Big single-day gainers (REJECTED: different mechanism — post-pop drift vs sustained rotation)
  - Intermediate Momentum pullback to 50 SMA (REJECTED: absolute momentum, not relative quartile transition)

## Rules (exact, unambiguous)
- **Universe:** ~150 liquid NSE equities from the cached panel (nifty_research_150_5y.pkl),
  same as strategies 003-008. Liquidity floor: turnover_60d >= ₹25cr/day.
- **Structural filter:** Close > SMA(200) — only buy names in a long-term uptrend.
- **Feature:** RS_20d = (stock 20-day return) − (Nifty 50 20-day return). Rank cross-sectionally
  each day. Compute the stock's percentile rank within all valid stocks on that day.
- **Entry signal:** TODAY's RS percentile rank >= 75th percentile (top quartile) AND the stock
  was in the bottom 25th percentile of RS at ANY point in the prior 15 bars.
  This is an indicator signal (computed from daily closes), so entry at same close is fine per §4.
- **Entry fill:** Same close (indicator-based daily signal).
- **Exit:** Fixed time horizon of 8 trading days, with 2×ATR stop loss, 2×ATR target.
- **Holding period:** 8 bars.
- **Costs:** charge_costs=True (always).

## Kill criteria — decided NOW, before any number
- Reject if stable mean z_paired < 2.0 across ≥20 control seeds.
- Reject if net edge ≤ 0 after costs.
- Reject if the most recent walk-forward fold has significantly negative z_paired.
- Reject if mid/small subgroup (the tradeable tier) fails to clear z_paired ≥ 2.0 alone (§8).
- This is the 9th strategy tested in this project + 14 inherited from the sister project = ~23
  total. A borderline pass (mean_z 2.0-2.2, low pass rate) is INCONCLUSIVE pending OOS test (§9).

## Threshold handling
- [x] The quartile thresholds (25th/75th percentile) are pre-committed from the cross-sectional
  momentum literature (standard academic quartile sorts). The 20-day lookback is a standard
  monthly momentum convention (Jegadeesh & Titman). No threshold search planned.
- [ ] If the result is weak, I will NOT scan alternative lookbacks to find a better one — that
  would be fitting, and the project already has 20+ dead candidates to deflate against.

---

## Results (after running)

Command(s) run:
```
python strategies/009_relative_strength_rotation_vs_nifty_quartile_acceleration.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 1098 |
| Paired days | 655 |
| Net edge vs control /trade | +0.232% |
| **naive z (edge_vs_control)** | 1.56 (p=0.118) _(optimistic)_ |
| **DAY-CLUSTERED z_paired (single draw)** | +1.04 (day_edge +0.160%) |
| **MEAN z_paired across 20 control seeds** | **+1.99 (min +1.11, max +3.00)** |
| Pass rate (seeds with z_paired >= 2.0) | **50.0%** (coin-flip, not robust) |
| Per-fold z_paired | F1: +1.62, F2: +0.61, F3: +0.85, **F4: +3.41** |
| Most-recent fold net edge | +0.02% net, +0.77% edge |
| Robust to +/-1 threshold step? | NO - gradient not plateau (80/20: 2.54, 75/25: 1.04, 70/30: 0.25) |
| Search-deflated? | No search conducted; thresholds pre-committed |
| Mid/Small subgroup (S8) | stable mean_z +1.58 (25% pass) - FAILS alone |
| Large cap subgroup (S8) | z_paired +1.16 - FAILS alone |

## Bias hunt - what could be faking this?
1. **Day-clustering partially addressed**: RS is relative to Nifty, so it does partially immunize
   against market-beta clustering. The 655 paired days is much higher than typical (vs ~100 for
   oversold strategies), meaning the signal fires broadly. But the day_edge is only +0.160%.
2. **No look-ahead**: Entry at same close is correct for indicator signals (RS is computed from
   closes). The cross-sectional rank on day T uses only data up to day T.
3. **No overlap inflation**: `allow_overlap=False` (default).
4. **Costs charged**: 0.50% avg round-trip (correct for this liquidity tier).
5. **Threshold gradient, not plateau**: The edge increases monotonically with tighter quartiles
   (80/20 > 75/25 > 70/30). This is a gradient, not a plateau. However, the 80/20 single-draw
   z_paired of 2.54 is from ONE control draw - the stable mean could easily be lower. The
   pre-committed 75/25 threshold failed; switching to 80/20 now would be threshold fitting (S6).
6. **Subgroup failure (S8)**: Neither mid/small (1.58) nor large caps (1.16) clear the bar alone.
   The pooled 1.99 is power from combining, not a stronger signal.
7. **Walk-forward inconsistency**: Only Fold 4 (most recent) clears 2.0 at +3.41. Folds 2 and 3
   are weak (0.61, 0.85). This is exactly the 002/005 pattern: one fold carries the average.

## VERDICT
**REJECT** - stable mean z_paired +1.99 < 2.0, 50% pass rate (coin flip), both subgroups fail
alone (mid/small +1.58, large-cap +1.16), 2/4 walk-forward folds weak. The sensitivity ladder
shows a fitted gradient, not a robust plateau. This is strategy #9 in the current project + ~14
inherited = ~23 total candidates tested, further deflating any borderline result.

Logged to `REJECTED.md` via `ledger.py reject`.

