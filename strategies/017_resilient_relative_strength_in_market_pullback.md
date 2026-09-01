# Strategy 017 — Resilient Relative Strength in Market Pullback

---

## Hypothesis
In liquid Indian equities (turnover >= ₹25cr/day), when the broader market index experiences a multi-day pullback (5-day market return <= -1.0%), stocks in a confirmed structural uptrend (Close > SMA 50 and SMA 50 > SMA 200) that demonstrate strong relative strength divergence (5-day return outperforming the market by >= 4.0%) reflect aggressive institutional accumulation and supply absorption. When the broader market selling pressure abates, these resilient leaders experience continuation momentum over the subsequent 6-10 trading days.

**Why the edge would exist:** In Indian markets, institutional funds accumulate high-conviction leaders during index pullbacks when liquidity is available. Strong divergence against general selling pressure indicates heavy sponsorship and a lack of overhead resistance once market pressure lifts.

**Why it might be fake:** (1) Market Beta clustering: even with RS relative to the index, trades trigger on market pullback days and could just be taking on higher beta risk. (2) Subgroup dependence: the edge might work only in Mid/Small caps during bull phases and collapse in bear regimes or large caps. (3) Friction wall: round-trip costs of ~0.50% can eat the modest gross drift.

## Checked against REJECTED.md?
- [x] Not present, not a trivial variant. Distinct from:
  - 009 RS Rotation (tested Q1->Q4 rotation; this tests resilience specifically *during index pullback*).
  - 007 NR4 Breakout & 015 50-day Breakout (breakouts, not index-divergence pullbacks).
  - 001/008 RSI mean-reversion (oversold dips, not relative strength divergence).

## Rules (exact, unambiguous)
- **Universe:** 88 liquid NSE equities (Nifty 500 / F&O watchlist), turnover_60d >= ₹25cr/day.
- **Structural filter:** Close > SMA(50) and SMA(50) > SMA(200) (confirmed structural uptrend).
- **Market condition:** 5-day return of broad market proxy <= -1.0% (market pullback).
- **Stock signal:** 5-day stock return − 5-day market return >= +4.0% (resilient relative strength).
- **Entry fill:** Same close (indicator signal calculated at EOD).
- **Exit:** Fixed holding period of 8 trading days (swing horizon), 2×ATR stop, 2×ATR target.
- **Holding period:** 8 bars.
- **Costs:** charge_costs=True (0.50% round-trip including liquidity impact).

## Kill criteria — decided NOW, before any number
- Reject if stable mean z_paired < 2.0 across ≥20 control seeds.
- Reject if net edge ≤ 0 after costs.
- Reject if the most recent walk-forward fold has negative paired z or negative net edge.
- Reject if mid/small subgroup (the tradeable tier) fails to clear z_paired ≥ 2.0 alone (§8).

## Threshold handling
- [x] Thresholds pre-committed: Market pullback <= -1.0%, Relative Strength >= +4.0%, Holding period = 8 bars. No tuning performed prior to commitment.

---

## Results (after running)

Command(s) run:
```bash
python strategies/017_resilient_relative_strength_in_market_pullback.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping, Pooled) | 926 |
| Paired days (Pooled) | 212 |
| Net avg/trade (Pooled) | +0.095% |
| Control (random) | -0.161% |
| Net edge vs control /trade (Pooled) | +0.255% |
| **naive z (edge_vs_control)** | 1.55 (p=0.1217) _(optimistic)_ |
| **DAY-CLUSTERED z_paired (single draw, Pooled)** | +1.03 (day_edge +0.224%) |
| **MEAN z_paired across 20 control seeds (Pooled)** | **+0.43 (min -0.90, max +1.16)** |
| Pass rate (seeds with z_paired >= 2.0, Pooled) | **0.0%** |
| Mid/Small subgroup trades | 516 trades, 151 paired days |
| Mid/Small net avg / net edge | Net avg +0.313%, Net edge +0.479% |
| **Mid/Small stable mean z_paired (20 seeds)** | **+1.94 (min +0.79, max +2.78, 45.0% pass rate)** |
| Large cap subgroup stable mean z_paired | **-1.65 (min -2.85, max -0.11, 0.0% pass rate)** |
| Walk-forward 4-fold z_paired (Mid/Small) | F1: +2.28, F2: +1.90, **F3: -0.18, F4: +0.85** |
| Most-recent fold (F4) net edge | Net avg -0.72%, Net edge -0.18% |
| Robust to ±1 threshold step? | No - steep dropoff on nearby parameter variations |

## Bias hunt — what could be faking this?
1. **Look-ahead**: None. Market return and stock returns use historical 5-day closes up to bar $i$.
2. **Overlap**: `allow_overlap=False` strictly enforced.
3. **Day-clustering**: Day-clustering crushes the pooled naive z (1.55 -> stable mean 0.43). In Mid/Small caps, stable mean z is +1.94, but only 45% of seeds cross 2.0 (coin-flip).
4. **Subgroup failure (§8)**: Large caps completely fail (stable mean z -1.65, net return -0.181%). Mid/Small caps alone fail the 2.0 bar on average (1.94 < 2.0).
5. **Decay / Regime instability (§7)**: Walk-forward splits show the edge was present in 2021-2023 (F1 +2.28, F2 +1.90) but completely evaporated in 2024-2026 (Fold 3 z -0.18, Fold 4 net return -0.72%, net edge -0.18%).

## VERDICT
**REJECT** — stable mean z_paired +0.43 pooled, +1.94 in mid/small caps (only 45% pass rate), completely fails in large caps (-1.65), and dies in recent walk-forward folds (F3 z -0.18, F4 net -0.72%).

If REJECT → added a row to `REJECTED.md`? [x]

