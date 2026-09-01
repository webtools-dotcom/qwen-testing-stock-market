# Strategy 010 — 3-Day Downside Accelerating Climax in Uptrend

---

## Hypothesis
In liquid Indian equities (turnover >= ₹25cr/day), when an equity in an established primary
uptrend (Close > SMA 200) suffers 3 consecutive days of accelerating percentage losses
(ret[t] < ret[t-1] < ret[t-2] < 0) with a 5-day drop < -6%, retail stop-losses cascade
simultaneously. This represents a short-term panic liquidation / capitulation climax. As selling
exhausts, institutional dip-buyers absorb the forced selling, generating a sharp mean-reverting
swing rebound over the subsequent 6–10 trading days.

## Checked against REJECTED.md?
- [x] Not present, not a trivial variant of a rejected idea.

## Rules (exact, unambiguous)
- **Universe:** 150 liquid NSE equities (Nifty Research 150 panel, 5y daily history, turnover >= ₹25cr/day).
- **Entry signal:** `ret[t] < ret[t-1] < ret[t-2] < 0` AND `roc_5 < -6.0%` AND `close > sma_200` AND `turnover_60d >= 25e7`. Known at bar `t` close.
- **Entry fill:** Same close fill (`simulate_trades(allow_overlap=False, charge_costs=True)`).
- **Exit:** Fixed holding period of 7 days (horizon=7).
- **Costs:** `charge_costs=True` (round-trip cost ~0.50% charged).

## Kill criteria — decided BEFORE running
- REJECT if stable mean `z_paired < 2.0`, OR net edge ≤ 0, OR it dies in the most recent walk-forward fold (Fold 4), OR mid/small subgroup fails alone (§8).

## Threshold handling
- Thresholds (`roc_5 < -6%`, 3-day acceleration) pre-committed based on capitulation dynamics. Sensitivity ladder tested at -4%, -6%, -8%.

---

## Results

Command run:
```bash
python strategies/010_3_day_downside_accelerating_climax_in_uptrend.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 129 |
| Paired days | 85 |
| Gross avg/trade | +1.587% |
| Avg round-trip cost | 0.500% |
| Net avg/trade | +1.087% |
| Control avg (random) | -0.202% |
| Net edge vs control /trade | +1.289% |
| **naive z (edge_vs_control)** | **+2.80** (p=0.0051) _(OPTIMISTIC — do not headline!)_ |
| **DAY-CLUSTERED z_paired (single draw)** | **+1.29** |
| **MEAN z_paired across 20 control seeds** | **+0.89** _(bar is ≥ 2.0 on the mean)_ |
| Pass rate (seeds with z_paired ≥ 2.0) | **0.0%** |
| Subgroup Mid/Small Caps Alone (§8) | Stable mean z: **+0.06** (Pass rate: 0.0%) |
| Subgroup Large Caps Alone | z_paired: +3.13 (N=35) |
| Walk-Forward Fold 1 (2023-04 to 2024-02) | z_paired +1.35 (Net +2.18%) |
| Walk-Forward Fold 2 (2024-02 to 2024-12) | z_paired -0.08 (Net +1.65%) |
| Walk-Forward Fold 3 (2024-12 to 2025-10) | z_paired -0.76 (Net -0.03%) |
| **Walk-Forward Fold 4 (Most Recent: 2025-10 to 2026-08)** | **z_paired -0.03** (Net -0.75%) |
| Robust to ±1 threshold step? | No — 5d RoC < -4% drops net to +0.21%, z_paired to +0.58 |

## Bias hunt — what could be faking this?
1. **Naive z vs Day-Clustered z gap:** Naive Welch z of +2.80 collapses to day-clustered z_paired of +1.29 on a single seed, and +0.89 across 20 seeds. The naive z was an artifact of trades piling onto market sell-off days.
2. **Pooling Artifact (§8):** The tradeable Mid/Small cap subgroup alone yields a stable mean z_paired of only +0.06 (0% pass rate). The gross return in large caps (+1.16%) carried the pooled sample size, but mid/small caps show zero edge over random control.
3. **Decay / Recent Fold Failure:** Edge decays significantly in recent folds: Fold 3 net -0.03% (z_paired -0.76) and Fold 4 (most recent 2025-2026 fold) net -0.75% (z_paired -0.03). The positive mean was driven entirely by Fold 1 (2023-2024 bull run market beta).

## VERDICT
**REJECT** — Stable mean z_paired of +0.89 (< 2.0 bar, 0% pass rate across 20 control seeds), Mid/Small cap subgroup fails alone (mean z_paired +0.06), and the edge is negative in the most recent walk-forward fold (Fold 4 net -0.75%, z_paired -0.03).

Logged to `REJECTED.md` via `ledger.py`.
