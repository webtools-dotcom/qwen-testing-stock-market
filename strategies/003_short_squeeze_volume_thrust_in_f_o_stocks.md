# Strategy 003 — Short-Squeeze Volume Thrust in F&O Stocks

---

## Hypothesis
In liquid NSE F&O stocks (turnover ≥ ₹25cr/day), when a stock that has experienced a sharp 5-day decline (5-day RoC < -5%) suddenly explodes upward (> +2.5% daily gain) on massive volume (> 2.0x 20-day median volume) and closes in the top quartile of its daily range (close-low / range > 0.75), it is hypothesized that short-covering capitulation and aggressive institutional absorption will initiate a sustained 6–10 day momentum rebound.

## Checked against REJECTED.md?
- [x] Checked against `REJECTED.md`: Related to big single-day gainers / post-pop drift (which failed in cash stocks), but here specifically tested on F&O derivatives stocks with high open interest / short squeeze dynamics following a 5-day selloff.

## Rules (exact, unambiguous)
- **Universe:** 88 liquid NSE F&O eligible stocks, filtered for 60-day median turnover ≥ ₹25 crore/day.
- **Entry signal:** `roc_5.shift(1) < -5.0%` AND `daily_ret > +2.5%` AND `vol_ratio > 2.0` AND `bar_pos > 0.75` AND `close > sma_200` on daily close.
- **Entry fill:** Close of signal bar.
- **Exit:** 7-day time exit (horizon_days=7). Non-overlapping trades (`allow_overlap=False`).
- **Holding period:** 7 trading days.
- **Costs:** `charge_costs=True` (0.50% round-trip cost model).

## Kill criteria — decided NOW, before any number
- Reject if stable mean `z_paired` < 2.0 across 20 control seeds.
- Reject if net edge vs control ≤ 0.
- Reject if the strategy fails in the most recent walk-forward fold.

---

## Results (after running)

Command run:
```bash
python strategies/003_short_squeeze_volume_thrust_in_f_o_stocks.py
```

| Metric | Value |
|---|---|
| Usable stocks | 88 liquid F&O stocks |
| Trades (non-overlapping) | 77 |
| Paired days | 54 |
| Gross avg/trade | +2.354% |
| Avg round-trip cost | 0.500% |
| **NET avg/trade** | **+1.854%** |
| Control (random) net/trade | −0.202% |
| **Net edge vs control /trade** | **+2.056%** |
| **naive z (edge_vs_control)** | 3.15 (p = 0.0016) *(optimistic, not the headline)* |
| **DAY-CLUSTERED z_paired (seed 42)** | **+0.77** |
| **STABLE 20-SEED mean_z** | **1.05 (min 0.41, max 1.80, pass_rate 0.0%)** |
| Win rate | 61.0% |
| Sharpe (annualised) | 2.11 |
| Most-recent fold net edge | **−3.01% (Fold 4: Net −3.79%, z_paired −2.18, DayEdge −2.25%)** |

### Walk-Forward Splits (Purged & Embargoed)

| Fold | Date Range | Trades | Net Avg | Control Net | Net Edge | z_paired | Day Edge |
|---|---|---|---|---|---|---|---|
| Fold 1 | 2023-04-13 to 2024-02-14 | 9 | +1.45% | +0.52% | +0.93% | +0.62 | +1.10% |
| Fold 2 | 2024-02-15 to 2024-12-19 | 37 | +4.59% | -0.21% | +4.80% | +2.20 | +1.87% |
| Fold 3 | 2024-12-20 to 2025-10-21 | 9 | -0.56% | -0.12% | -0.44% | -0.34 | -0.58% |
| Fold 4 (Recent) | 2025-10-23 to 2026-08-20 | 7 | -3.79% | -0.78% | **-3.01%** | **-2.18** | **-2.25%** |

## Bias hunt — what explains this failure?
1. **Single-Period / Regime Fluke:** Strategy performance was carried almost exclusively by the 2024 general bull run (Fold 2: net +4.59%, z_paired 2.20), where virtually any high-beta long trade made money.
2. **Recent Decay & Failure:** In normal/choppy regimes (Folds 3 and 4), short-squeeze bursts quickly exhausted and resumed downward momentum. In the most recent fold (Fold 4), the strategy suffered a severe loss (Net -3.79%/trade, paired z -2.18).
3. **Day-Clustering & Multi-Seed Control Failure:** Across 20 random control seeds, mean z_paired is only 1.05 with a 0.0% pass rate. The naive z (3.15) was a statistical illusion caused by clustered trade days in 2024.

## VERDICT
**REJECT** — Fails stable control bar (`mean_z = 1.05 < 2.0`, 0% pass rate across 20 seeds) and severely fails in the most recent walk-forward fold (Fold 4: Net −3.79%, $z_{\text{paired}} = -2.18$).

Logged to `REJECTED.md`:
```bash
python ledger.py reject "Short-Squeeze Volume Thrust in F&O Stocks" "stable mean_z 1.05 (0% pass rate), dies in recent fold (net -3.79%, z_paired -2.18)"
```
