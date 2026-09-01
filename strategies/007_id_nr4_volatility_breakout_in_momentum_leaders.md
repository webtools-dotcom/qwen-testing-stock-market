# Strategy 007 — Inside-Day NR4 Volatility Breakout in Momentum Leaders

---

## Hypothesis
In liquid Indian equities (turnover ≥ ₹25cr/day), when an intermediate relative strength leader (`momentum_60d > 15%`, `SMA 50 > SMA 200`, `Close > SMA 50`) prints an Inside-Day Narrowest Range of 4 sessions (ID/NR4)—representing complete order-flow equilibrium and temporary volatility compression—a breakout above the previous session's high (`Close > High[t-1]`) accompanied by expanding volume (`Volume > 1.2x 20-day median`) signals institutional accumulation and trend expansion, producing a positive swing edge over 6–10 trading days.

## Checked against REJECTED.md?
- [x] Not present in `REJECTED.md`.
  - Distinct from VCP / unconstrained consolidation breakouts (which failed across all cap tiers).
  - Distinct from 3-day volatility contraction pullbacks to 50 SMA (which buys pullbacks rather than directional expansion).
  - Distinct from oversold mean reversion (RSI is in positive expansion territory 50–65).

## Rules (exact, unambiguous)
- **Universe:** 88 liquid NSE equities, filtered for 60-day median turnover ≥ ₹25 crore/day (5-year daily panel).
- **Entry signal:** `ID_NR4[t-1]` AND `Close[t] > High[t-1]` AND `Volume[t] > 1.2 * Volume_Med_20[t]` AND `Mom_60 > 15.0%` AND `Close[t] > SMA 50` AND `SMA 50 > SMA 200` on daily close.
- **Entry fill:** Same close (standard EOD indicator fill; next-open also tested).
- **Exit:** 7-day holding horizon (`horizon_days=7`). Non-overlapping trades (`allow_overlap=False`).
- **Holding period:** 7 trading days.
- **Costs:** `charge_costs=True` (Indian round-trip cost model: 0.40% baseline + liquidity impact).

## Kill criteria — decided NOW, before any number
- Reject if stable mean `z_paired` < 2.0 across 20 control seeds.
- Reject if net edge vs control ≤ 0.
- Reject if the strategy fails or shows negative paired z in walk-forward folds.
- Reject if the tradeable subgroup (Mid/Small caps per §8) does not clear the bar on its own.
- Reject if execution at next-open is net negative.

## Threshold handling
- [x] Pre-committed momentum threshold at 15.0% and volume multiplier at 1.2x.
- [x] Scanned momentum ladder (5%–30%) with Deflated Sharpe (DSR) and effective trials.

---

## Results (after running)

Command run:
```bash
python strategies/007_id_nr4_volatility_breakout_in_momentum_leaders.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 228 |
| Paired days | 175 |
| Gross avg/trade | +0.562% |
| Avg round-trip cost | 0.500% |
| **NET avg/trade** | **+0.062%** |
| Control (random) net/trade | −0.202% |
| **Net edge vs control /trade** | **+0.264%** |
| **naive z (edge_vs_control)** | **0.89** (p = 0.376) *(optimistic, not the headline)* |
| **DAY-CLUSTERED z_paired (single draw)** | **+0.95** (175 paired days, day_edge +0.294%) |
| **MEAN z_paired across ≥20 control seeds** | **+1.45 (min 0.93, max 1.95, pass_rate 0.0%)** |
| Win rate | 51.8% |
| Sharpe (annualised) | 0.08 |
| Next-open fill | Trades=227, **Net=−0.10%**, Edge=+0.05%, mean_z=+0.93 (pass 0%) |
| Large caps alone | Trades=98, Net=+0.08%, Edge=+0.15%, stable mean_z=+0.06 (pass 0%) |
| Mid/Small subgroup alone (§8) | Trades=130, Net=+0.05%, Edge=+0.25%, stable mean_z=+1.40 (pass 7%) |
| Deflated Sharpe (DSR) | DSR = 0.9995 (Effective trials = 5.71, Noise ceiling = 0.16) |

### Walk-Forward Splits (Purged & Embargoed)

| Fold | Date Range | Trades | Net Avg | Control Net | Net Edge | z_paired | Day Edge |
|---|---|---|---|---|---|---|---|
| Fold 1 | 2022-06-23 to 2023-04-12 | 68 | +0.92% | +0.03% | +0.89% | +2.11 | +1.15% |
| **Fold 2** | 2023-04-13 to 2024-02-14 | 56 | -0.32% | +0.19% | **−0.51%** | **−0.76** | **−0.46%** |
| **Fold 3** | 2024-02-15 to 2024-12-19 | 24 | -0.40% | -0.35% | **−0.05%** | **−0.97** | **−0.87%** |
| Fold 4 (Recent) | 2024-12-20 to 2026-08-21 | 44 | -0.26% | -0.44% | +0.18% | +1.83 | +1.49% |

### Parameter Ladder Sweep (Momentum Threshold Gradient)

| Mom_60 Threshold | Trades | Net Avg% | z_naive | z_paired | mean_z (20s) | Pass Rate |
|---|---|---|---|---|---|---|
| 5.0% | 399 | +0.10% | 1.42 | 0.43 | 0.95 | 0% |
| 10.0% | 317 | +0.03% | 0.94 | 0.65 | 1.14 | 10% |
| 15.0% (Pre-committed) | 228 | +0.06% | 0.89 | 0.95 | 1.42 | 0% |
| 20.0% | 162 | +0.28% | 1.38 | 1.23 | 2.06 | 60% |
| 25.0% | 108 | +0.07% | 0.59 | 0.80 | 1.24 | 10% |
| 30.0% | 78 | +0.16% | 0.68 | 0.26 | 1.19 | 10% |

---

## Bias hunt — what explains this failure?

1. **Failure to Clear Day-Clustered Headline Bar:**
   - The stable mean $z_{\text{paired}}$ across 20 independent control seeds is only **+1.45** (with a **0.0% pass rate** to clear the $\ge 2.0$ bar).
   - In single draws, $z_{\text{paired}}$ hovers between 0.93 and 1.95, failing to demonstrate statistically robust stock-selection alpha over market beta.
2. **Transaction Cost Barrier:**
   - While gross average return is $+0.562\%$, Indian equity round-trip costs ($0.500\%$) reduce net edge to an economically negligible $+0.062\%$ per trade.
   - When filled at next open (realistic market-open execution), net return falls into the negative territory (**−0.10% net loss**).
3. **Walk-Forward Inconsistency:**
   - 2 out of 4 walk-forward folds exhibit negative net edges and negative paired z-scores (Fold 2: $z_{\text{paired}} = -0.76$, Fold 3: $z_{\text{paired}} = -0.97$).
4. **Subgroup Failure (§8 of METHODOLOGY.md):**
   - Large caps show zero signal ($z_{\text{paired}} = +0.06$, pass rate 0%).
   - Mid/Small caps alone only reach stable mean $z_{\text{paired}} = +1.40$ (pass rate 7%), failing to clear the bar independently.

---

## VERDICT
**REJECT** — The strategy produces a stable mean $z_{\text{paired}} = 1.45$ (0% pass rate across 20 control seeds), net edge of only $+0.062\%$ which collapses to a net loss of $-0.10\%$ under next-open execution, and fails 2 of 4 walk-forward folds.

Logged to `REJECTED.md`:
```bash
python ledger.py reject "Inside-Day NR4 Volatility Breakout in Momentum Leaders" "stable mean_z 1.45 (0% pass rate), 2/4 walk-forward folds negative, next-open net loss (-0.10%)"
```

