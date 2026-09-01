# Strategy 028 — Volume-Dryup Pullback in Trend Consistency Leaders in Mid-Small Caps

---

## Hypothesis
In Indian mid/small caps, institutional trend leaders (top 15% of 60-day Risk-Adjusted Return / Sharpe) experience brief 2-4 day pullbacks due to transient market fluctuations or retail profit-taking. When a pullback occurs with a dramatic Volume Dry-Up (daily volume < 70% of its 20-day SMA), it signals an absence of institutional selling / overhead supply exhaustion (liquidity absorption). As the pullback exhausts on low volume, the underlying institutional drift re-asserts itself over a 6-10 day swing holding horizon (baseline h=8 sessions).

## Checked against REJECTED.md?
- [x] Not present, not a trivial variant of a rejected idea.

## Rules (exact, unambiguous)
- **Universe:** Liquid NSE names not in the Nifty 50; 60-day median turnover $\ge \text{₹}25\text{ cr}$.
- **Entry signal:** Known at close $t$:
  1. `sharpe60_rank >= 0.85`: Trailing 60-day annualized Sharpe ratio in top 15% cross-sectionally.
  2. `ret3 < -1.0%`: 3-day trailing return is negative (pullback $\le -1.0\%$).
  3. `vol_ratio1 < 0.70`: Current session volume $< 70\%$ of 20-day SMA volume (volume dry-up).
  4. `close > sma_50`: Stock remains in structural medium-term uptrend above its 50-day SMA.
- **Entry fill:** Same close (EOD signal); Next-open entry fill tested as execution fragility check.
- **Exit:** Pure time exit at 8 trading sessions (with 6, 10, 12 sessions tested for horizon stability).
- **Holding period:** 8 sessions (~1.5 weeks).
- **Costs:** `charge_costs=True` (liquidity-tiered cost model, ~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode per stock).

## Kill criteria — decided NOW, before any number
- Reject if stable mean $z_{\text{paired}} < 2.0$ across 20 control seeds (pooled) OR $< 2.0$ on the hold-out half B of names.
- Reject if net day edge $\le 0$ in any regime block or chronological walk-forward fold.
- Reject if survivorship test fails: Pre-2017 listings alone must clear stable mean $z_{\text{paired}} \ge 2.0$.
- Reject if parameter sensitivity shows an unstable spike rather than a plateau.
- Reject if the 20-slot cash-constrained portfolio fails the economic viability test (loses severely to Buy-and-Hold or degrades to unviable levels at 1.5x transaction costs).

## Threshold handling
- Scanned thresholds across Sharpe rank (80%, 85%, 90%), Volume Dry-Up (0.60, 0.70, 0.80), and Pullback depth (-0.5%, -1.0%, -1.5%). Checked full 27-cell grid for monotonic plateau.

---

## Results (after running)

Command(s) run:
```bash
python strategies/028_volume_dryup_pullback_in_trend_consistency_leaders_in_mid_small_caps.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 3,820 |
| Paired days | 1,594 |
| Gross return / trade | +1.081% |
| Round-trip cost | 0.500% |
| Net return / trade | +0.581% |
| Control return (random) | +0.402% |
| Net edge vs control / trade | +0.178% |
| Naive z (edge vs control) | 1.17 (p = 0.243) |
| **DAY-CLUSTERED z_pair (Seed 42)** | **+2.56** (Day edge: +0.457%) |
| **MEAN z_paired across 20 control seeds** | **+2.87** (min 1.34, max 3.66) |
| Pass rate (seeds with z_paired $\ge 2.0$) | **95.0%** |
| Holdout Half B stable mean z | **1.54 (Pass rate: 25.0%)** — **KILLED** |
| Pre-2017 listings alone (survivorship) | **0.91 (Seed 42 z = -0.57, Pass rate: 5.0%)** — **KILLED** |
| Horizon 6 sessions | Net +0.069%, Day Edge +0.326%, Mean z = 1.64 (30% pass) |
| Horizon 8 sessions | Net +0.581%, Day Edge +0.478%, Mean z = 2.78 (90% pass) |
| Horizon 10 sessions | Net +0.817%, Day Edge +0.575%, Mean z = 2.86 (90% pass) |
| Horizon 12 sessions | Net +1.095%, Day Edge +0.736%, Mean z = 2.80 (90% pass) |
| Next-Open Fill (Execution Check) | Trades 3,820, Net +0.408%, Day Edge +0.591%, z = +3.40 |
| Walk-Forward Fold 1 (2018–2020) | Day Edge +0.854%, z = +1.23 |
| Walk-Forward Fold 2 (2020–2022) | Day Edge +0.427%, z = +0.96 |
| Walk-Forward Fold 3 (2022–2024) | **Day Edge -0.142%, z = -0.49** — **KILLED** |
| Walk-Forward Fold 4 (2024–2026) | Day Edge +0.630%, z = +2.87 |
| **Portfolio Tool Test (20 slots, 1.0x costs)** | **CAGR +8.40%, Sharpe 0.57, MaxDD -30.66% vs B&H CAGR +18.87%, Sharpe 0.97** — **KILLED** |
| **Portfolio Tool Test (20 slots, 1.5x costs)** | **CAGR +3.36%, Sharpe 0.28, MaxDD -34.86%** |
| **Portfolio Tool Test (20 slots, 2.0x costs)** | **CAGR -1.45%, Sharpe -0.00, MaxDD -46.49%** |

## Bias hunt — what killed this strategy?
1. **Hold-out Half B Failure:** While pooled names produced $z_{\text{paired}} = 2.87$, testing Half B alone collapsed to mean $z = 1.54$ (only 25% seed pass rate), violating §8 cross-validation independence.
2. **Survivorship Bias:** Pre-2017 listings alone collapsed to mean $z = 0.91$ ($z = -0.57$ on Seed 42, 5% pass rate). The apparent pooled edge was entirely concentrated in newer listings post-2017.
3. **Walk-Forward Inconsistency:** Fold 3 (2022–2024) posted a negative day edge ($-0.142\%$, $z = -0.49$).
4. **Fatal Turnover Drag / Economic Unviability:** An 8-session holding period generates ~380 portfolio trades/year across 20 slots. With average net return of only $+0.58\%$ per trade, round-trip friction ($0.50\%$) drains 9.5% per year of NAV. The resulting portfolio return (+8.40% CAGR, Sharpe 0.57) lags simple buy-and-hold (+18.87% CAGR, Sharpe 0.97) by over 1,000 bps/year and collapses to +3.36% at 1.5x costs.

## VERDICT
**REJECT** — Day-clustered pooled $z_{\text{paired}} = +2.87$, but fails hold-out half B ($z = 1.54$), fails pre-2017 survivorship ($z = 0.91$), fails walk-forward Fold 3 ($z = -0.49$), and suffers fatal turnover drag in portfolio simulation (+8.40% CAGR vs +18.87% Buy & Hold, collapsing to +3.36% at 1.5x costs).

Added a row to `REJECTED.md`? [x]

