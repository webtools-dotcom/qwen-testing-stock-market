# Strategy 006 — 3-Day Volatility Contraction Pullback to 50 SMA

---

## Hypothesis
In liquid Indian equities (turnover ≥ ₹25cr/day), when an intermediate relative strength leader (`momentum_60d > 20%`, `SMA 50 > SMA 200`, `Close > SMA 200`) stages an orderly pullback into its 50-day SMA institutional benchmark (`Low <= 1.01 * SMA 50`, `Close >= SMA 50`) accompanied by 3 consecutive sessions of contracting daily bar range (`Range[t] < Range[t-1] < Range[t-2]`), it signals that selling pressure has dried up (liquidity exhaustion and absence of institutional supply) directly at key institutional trend support. As dip-buyers re-enter at the 50 SMA support, the stock resumes its primary upward trend, producing a positive swing edge over 6–10 trading days.

## Checked against REJECTED.md?
- [x] Not present in `REJECTED.md`.
  - Distinct from unconstrained 50-SMA pullback (which failed without volatility contraction).
  - Distinct from momentum breakout / VCP (which buys high consolidation breakouts rather than buying at 50-SMA support).
  - Distinct from oversold mean reversion (RSI is in normal range 45–55, not oversold).

## Rules (exact, unambiguous)
- **Universe:** 88 liquid NSE equities, filtered for 60-day median turnover ≥ ₹25 crore/day (5-year daily panel).
- **Entry signal:** `Range[t] < Range[t-1] < Range[t-2]` AND `Low <= 1.01 * SMA 50` AND `Close >= SMA 50` AND `Mom_60 > 20.0%` AND `SMA 50 > SMA 200` AND `Close > SMA 200` on daily close.
- **Entry fill:** Same close (standard EOD indicator fill; next-open also verified).
- **Exit:** 7-day holding horizon (horizon_days=7). Non-overlapping trades (`allow_overlap=False`).
- **Holding period:** 7 trading days.
- **Costs:** `charge_costs=True` (Indian round-trip cost model: 0.40% baseline + liquidity impact).

## Kill criteria — decided NOW, before any number
- Reject if stable mean `z_paired` < 2.0 across 20 control seeds.
- Reject if net edge vs control ≤ 0.
- Reject if the strategy fails in the most recent walk-forward fold.
- Reject if trade sample size is insufficient (< 100 trades across 5 years).

## Threshold handling
- [x] Scanned parameter grid (Mom 10–25%, SMA dist 1.00–1.02) with Deflated Sharpe (DSR) and effective trials.

---

## Results (after running)

Command run:
```bash
python strategies/006_3_day_volatility_contraction_pullback_to_50_sma.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 58 |
| Paired days | 50 |
| Gross avg/trade | +2.443% |
| Avg round-trip cost | 0.500% |
| **NET avg/trade** | **+1.943%** |
| Control (random) net/trade | −0.202% |
| **Net edge vs control /trade** | **+2.144%** |
| **naive z (edge_vs_control)** | **3.41** (p = 0.00066) *(optimistic, not the headline)* |
| **DAY-CLUSTERED z_paired (single draw)** | **+2.67** (50 paired days, day_edge +1.674%) |
| **MEAN z_paired across ≥20 control seeds** | **+2.73 (min 1.96, max 4.07, pass_rate 95.0%)** |
| Win rate | 67.2% |
| Sharpe (annualised) | 2.44 |
| Most-recent fold net edge | +0.05% (Fold 4), but **z_paired = −0.88, day_edge = −0.81%** |
| Next-open fill | Trades=58, Net=+1.78%, Edge=+1.93%, mean_z=+2.52 (pass 90%) |
| Mid/Small subgroup alone (§8) | Trades=42, Net=+2.12%, Edge=+2.33%, stable mean_z=+2.60 (pass 87%) |
| Large caps alone | Trades=16, Net=+1.47%, Edge=+1.54%, stable mean_z=+0.99 (pass 0%) |
| Deflated Sharpe (DSR) | DSR = 1.0000 (Effective trials = 7.44) |

### Walk-Forward Splits (Purged & Embargoed)

| Fold | Date Range | Trades | Net Avg | Control Net | Net Edge | z_paired | Day Edge |
|---|---|---|---|---|---|---|---|
| Fold 1 | 2022-06-23 to 2023-04-12 | 12 | +2.84% | +0.03% | +2.81% | +1.76 | +2.18% |
| Fold 2 | 2023-04-13 to 2024-02-14 | 16 | +3.79% | +0.19% | +3.60% | +2.13 | +2.95% |
| Fold 3 | 2024-02-15 to 2024-12-19 | 3 | -0.46% | -0.35% | -0.11% | +0.64 | +0.64% |
| **Fold 4 (Recent)** | 2024-12-20 to 2026-08-21 | 8 | -0.39% | -0.44% | +0.05% | **−0.88** | **−0.81%** |

---

## Bias hunt — what explains this failure?

1. **Walk-Forward Fold Decay & Recent Regime Failure (THE KILLER):**
   - In Fold 4 (the most recent 2024–2026 walk-forward fold), the strategy generated a **negative paired z-score (z_paired = −0.88)** and a **negative day edge (−0.81%)**.
   - Performance was heavily concentrated in the historical 2022–2024 bull trend (Folds 1 and 2). When tested out-of-sample in recent market conditions, the edge evaporated.
2. **Severe Sample Size / Frequency Underpowering:**
   - Over a 5-year panel across 88 liquid stocks, the strict 3-day range contraction constraint at the 50 SMA generated only **58 total trades** (~11.6 trades per year).
   - In Fold 3, only 3 trades triggered; in Fold 4, only 8 trades triggered. A strategy generating < 1 trade per month does not carry sufficient sample size to establish statistical robustness.
3. **Session-Level Multiple Testing Search Context (§9 of METHODOLOGY.md):**
   - This setup was found after scanning 25+ candidate strategy families across 3 screening rounds in this session.
   - Per §9, a candidate with tiny n and negative recent fold from a broad search is a classic false discovery.

---

## VERDICT
**REJECT** — While the pooled historical mean $z_{\text{paired}} = 2.73$ appears strong, the strategy completely fails in the most recent walk-forward fold (Fold 4: $z_{\text{paired}} = -0.88$, day edge $-0.81\%$), suffers from severe trade frequency collapse (only 58 trades in 5 years, with $n=3$ and $n=8$ in recent folds), and emerged from a large 25+ multi-strategy search.

Logged to `REJECTED.md`:
```bash
python ledger.py reject "3-Day Volatility Contraction Pullback to 50 SMA" "stable mean_z 2.73 pooled, but dies in recent fold (Fold 4 z_paired -0.88, day_edge -0.81%), tiny sample size (58 trades in 5y)"
```

