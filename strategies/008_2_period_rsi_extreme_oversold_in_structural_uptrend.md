# Strategy 008 — 2-Period RSI Extreme Oversold in Structural Uptrend

---

## Hypothesis
In liquid Indian equities (60-day turnover $\ge$ ₹25cr/day), when an equity in an established primary structural uptrend ($\text{Close} > \text{SMA}_{200}$ and $\text{SMA}_{50} > \text{SMA}_{200}$) experiences sharp short-term selling causing the 2-period RSI to plunge into deep oversold territory ($\text{RSI}_2 < 5.0$), it represents a temporary micro-liquidation / retail stop run. Institutional dip-buyers step in to defend the primary trend, creating a positive mean-reverting swing rebound over the subsequent 6–10 trading days.

## Checked against REJECTED.md?
- [x] Checked `REJECTED.md` and `ADOPTED.md`.
  - Distinct from standard RSI(14)<30 (which requires sustained multi-week selling).
  - Distinct from unconstrained pullbacks (requires structural macro uptrend filters $\text{SMA}_{50} > \text{SMA}_{200}$).
  - Tests the prominent Larry Connors short-period RSI mean-reversion anomaly on the Indian equity market.

## Rules (exact, unambiguous)
- **Universe:** 88 liquid NSE equities, filtered for 60-day rolling turnover floor $\ge$ ₹25 crore/day (5-year panel, 2021–2026).
- **Entry signal:** $\text{RSI}_2 < 5.0$ AND $\text{Close} > \text{SMA}_{200}$ AND $\text{SMA}_{50} > \text{SMA}_{200}$ on daily close.
- **Entry fill:** Same close (standard daily indicator fill).
- **Exit:** Fixed time horizon of 7 trading days. Non-overlapping trades (`allow_overlap=False`).
- **Holding period:** 7 bars (swing horizon).
- **Costs:** `charge_costs=True` (0.40% baseline + 0.10% liquidity impact = 0.50% total round-trip deducted per trade).

## Kill criteria — decided before running
- Reject if stable mean $z_{\text{paired}} < 2.0$ across 20 control seeds.
- Reject if net edge $\le 0$ after deducting 0.50% round-trip costs.
- Reject if edge collapses or turns negative in walk-forward folds.
- Reject if Mid/Small cap tradeable subgroup fails on its own (§8).

## Threshold handling
- Pre-committed threshold $\text{RSI}_2 < 5.0$ from classic quantitative literature (Larry Connors).
- Scanned sensitivity ladder (2.0, 5.0, 8.0, 10.0, 15.0) and evaluated Deflated Sharpe Ratio (DSR).

---

## Results (after running)

Command run:
```bash
python strategies/008_2_period_rsi_extreme_oversold_in_structural_uptrend.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 1,320 |
| Paired days | 504 |
| Gross avg return / trade | +0.397% |
| Round-trip costs charged | 0.500% |
| **NET avg return / trade** | **-0.103%** |
| Control (random entry) net | -0.202% |
| **Net edge vs control / trade** | **+0.099%** |
| Win rate | 50.1% |
| Annualised Sharpe (7d hold) | -0.15 |
| **naive z (edge_vs_control)** | 0.79 ($p = 0.431$) *(optimistic, not headline)* |
| **DAY-CLUSTERED z_paired (single seed 42)** | **-1.08** (day_edge = -0.164%, 504 paired days) |
| **MEAN z_paired across 20 control seeds** | **-0.77** (min: -2.17, max: +0.13) |
| **Pass rate (seeds with $z_{\text{paired}} \ge 2.0$)** | **0.0%** (0 of 20 seeds pass) |
| Per-fold $z_{\text{paired}}$ (4 purged folds) | Fold 1: -0.51, Fold 2: -1.09, Fold 3: -0.45, Fold 4: +1.23 |
| Most-recent fold net edge (Fold 4) | -0.38% (net return), +0.40% (edge vs control), $z_{\text{paired}} = +1.23$ |
| Mid/Small subgroup alone (§8) | 619 trades, Net +0.08%, Stable mean $z = +0.73$ (0% pass rate) |
| Robust to $\pm 1$ threshold step? | No — all thresholds between 2.0 and 15.0 show negative/zero $z_{\text{paired}}$ ($\le +0.11$) |
| Deflated Sharpe Ratio (DSR) | $\text{DSR} = 0.0000$ across 5 trials |

### Parameter Sensitivity Ladder (RSI_2 Cutoff)
| RSI_2 Cutoff | Trades | Net Avg % | Edge vs Control | $z_{\text{paired}}$ | Sharpe |
|---|---|---|---|---|---|
| 2.0 | 533 | +0.27% | +0.47% | -0.07 | 0.38 |
| **5.0 (Base)** | **1,320** | **-0.10%** | **+0.10%** | **-1.08** | **-0.15** |
| 8.0 | 2,006 | -0.10% | +0.10% | -1.08 | -0.15 |
| 10.0 | 2,413 | -0.17% | +0.03% | -0.55 | -0.26 |
| 15.0 | 3,209 | -0.10% | +0.10% | +0.11 | -0.15 |

---

## Bias hunt — what killed this strategy?
1. **Frictional Cost Wall:** Gross average return is only +0.397%, which is completely swallowed by the standard 0.500% Indian round-trip execution cost stack (STT, brokerage, GST, exchange turnover charges, stamp duty, and bid-ask slippage). The strategy produces a negative net return of -0.103% per trade.
2. **Day-Clustering & Market Beta:** The naive trade-level $z$ of 0.79 collapses to a day-clustered $z_{\text{paired}}$ of **-1.08** (stable mean **-0.77** across 20 control seeds). The micro-dips occur on broad market down-drift days where stock selection adds zero excess alpha over a random entry.
3. **Walk-Forward Inconsistency:** 3 of the 4 chronological walk-forward folds produce negative $z_{\text{paired}}$ (Fold 1: -0.51, Fold 2: -1.09, Fold 3: -0.45), and Fold 4 fails to reach the 2.0 bar ($z_{\text{paired}} = 1.23$).
4. **Subgroup Failure (§8):** In Mid/Small caps, the stable mean $z$ is only +0.73 with a 0% pass rate.
5. **Absence of Edge Across Parameters:** Every single threshold tested on the parameter ladder produces an annualized Sharpe $\le 0.38$, negative/zero $z_{\text{paired}}$, and a Deflated Sharpe Ratio of 0.0000.

## VERDICT
**REJECT.** The strategy produces a negative net return of -0.103% per trade after friction, a day-clustered stable mean $z_{\text{paired}}$ of **-0.77** (0% pass rate across 20 seeds), fails 3 out of 4 walk-forward folds, and fails the Mid/Small subgroup on its own ($z = 0.73$).

Logged to `REJECTED.md` via `ledger.py`:
```bash
python ledger.py reject "2-Period RSI Extreme Oversold in Structural Uptrend" "stable mean_z -0.77 (0% pass rate), net -0.10% after costs, 3/4 walk-forward folds negative"
```
