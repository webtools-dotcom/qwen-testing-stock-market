# Strategy 029 — Intraday Absorption Pullback in Trend Consistency Leaders

---

## Hypothesis
In Indian mid/small caps, institutional trend leaders (top 15% of 252-day Trend Consistency / Information Ratio of trend: $\frac{\mu_{252}}{\sigma_{252}} \sqrt{252}$) experience brief multi-day pullbacks ($RSI(14) < 40$) due to transient broad market noise or sector rotation. When buyers absorb the selling intraday (forming a lower shadow/wick $\ge 35\%$ of total bar range or closing positive $Close > Open$), the underlying institutional accumulation reasserts itself, creating an accelerated upward rebound over a 6-10 day swing horizon (baseline $h=8$ sessions).

---

## Checked against REJECTED.md?
- [x] **Checked against REJECTED.md:**
  - 001 (rejected): Plain RSI<30 mean reversion (net edge eaten by costs).
  - 005 (provisional watch): Bullish hammer pin-bar (mid/small alone failed at $z=1.62$).
  - 013 (rejected): RSI 35 pullback in uptrend ($z = -0.65$).
  - 022 (rejected as swing): 12m momentum at 8d hold (turnover friction destroyed edge).
  - 028 (rejected): Volume dry-up pullback in 60d Sharpe leaders (failed Half B at $z=1.54$ and pre-2017 at $z=0.91$).
  - Strategy 029 specifically tests the interaction of **252-day Trend Consistency Leaders + RSI < 40 Pullback + Intraday Absorption (Lower Wick / Green Close)** on non-overlapping 8-session holds.

---

## Rules (exact, unambiguous)
- **Universe:** Liquid NSE names not in the Nifty 50; 60-day median turnover $\ge \text{₹}25\text{ cr}$.
- **Features (known at bar $t$ close):**
  1. `rank_trend >= 0.85`: Trailing 252-day trend consistency (annualized Sharpe of daily returns) in top 15% cross-sectionally.
  2. `rsi < 40`: RSI(14) in oversold/pullback territory.
  3. `lower_wick >= 0.35 | close > open`: Intraday price action shows absorption (lower shadow $\ge 35\%$ of high-low range OR green daily candle).
  4. `close > sma_200`: Structural long-term uptrend.
- **Entry fill:** Same close (indicator signal from daily bar). Next-open entry tested as mandatory execution fragility check.
- **Exit:** Pure time exit at 8 trading sessions (with 6, 10, 12 sessions tested for horizon stability).
- **Holding period:** 8 sessions (~1.5 weeks).
- **Costs:** `charge_costs=True` (liquidity-tiered model, ~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode per stock).

---

## Kill criteria — decided BEFORE running
REJECT if any of the following occur:
1. Stable mean $z_{\text{paired}} < 2.0$ across 20 control seeds (pooled) OR $< 2.0$ on the hold-out half B of names.
2. Net day edge $\le 0$ in any regime block or chronological walk-forward fold.
3. **Survivorship:** Pre-2017 listings alone must clear stable mean $z_{\text{paired}} \ge 2.0$.
4. **Execution Fragility:** Collapses or turns negative under next-session open entry fill.
5. **Portfolio Tool Test:** 20-slot cash-constrained portfolio with 0.50% round-trip costs fails the economic test (negative CAGR or loses severely to Buy-and-Hold).

---

## Results (after running)

Command run:
```bash
python strategies/029_intraday_absorption_pullback_in_trend_consistency_leaders.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 689 |
| Paired days | 428 |
| Gross avg return / trade | +0.495% |
| Avg round-trip cost | 0.500% |
| **NET avg return / trade** | **-0.005%** |
| Control avg return (random) | -0.234% |
| Net edge vs control / trade | +0.229% |
| Win rate | 51.2% |
| **DAY-CLUSTERED z_paired (seed 0)** | **+1.25** (Day edge: +0.283%) |
| **STABLE MEAN z_paired across 20 control seeds** | **+1.22** (min +0.50, max +1.62) — **KILLED** |
| **Pass rate (seeds with z_paired $\ge 2.0$)** | **0.0%** — **KILLED** |
| Holdout Half B stable mean z | **+0.68 (0% pass rate, Net -0.099%)** — **KILLED** |
| Pre-2017 listings alone (survivorship) | **+0.91 (0% pass rate, Net -0.060%)** — **KILLED** |
| Next-Open Entry (Execution Fragility) | **+0.43 (0% pass rate, Net -0.369%)** — **KILLED** |
| Horizon 6 sessions | Net -0.108%, Day Edge +0.259%, Mean z = +1.05 (0% pass) |
| Horizon 8 sessions | Net -0.005%, Day Edge +0.283%, Mean z = +1.25 (0% pass) |
| Horizon 10 sessions | Net -0.118%, Day Edge +0.149%, Mean z = +0.60 (0% pass) |
| Horizon 12 sessions | Net +0.020%, Day Edge +0.256%, Mean z = +0.87 (0% pass) |
| Walk-Forward Fold 1 (2018–2019) | Net -1.768%, Day Edge -0.292%, Mean z = **-1.17** — **KILLED** |
| Walk-Forward Fold 2 (2019–2021) | Net -1.830%, Day Edge +1.144%, Mean z = +1.08 |
| Walk-Forward Fold 3 (2021–2023) | Net +1.283%, Day Edge +1.472%, Mean z = +2.83 |
| Walk-Forward Fold 4 (2023–2024) | Net +1.254%, Day Edge -0.316%, Mean z = **-0.56** — **KILLED** |
| Walk-Forward Fold 5 (2024–2026) | Net -0.535%, Day Edge -0.067%, Mean z = **-0.38** — **KILLED** |
| **Portfolio Tool Test (20 slots, 1.0x costs)** | **CAGR -0.13%, Sharpe -0.02, MaxDD -18.52%** — **KILLED** |
| **Portfolio Tool Test (20 slots, 1.5x costs)** | **CAGR -0.99%, Sharpe -0.26, MaxDD -19.83%** |
| **Portfolio Tool Test (20 slots, 2.0x costs)** | **CAGR -1.84%, Sharpe -0.50, MaxDD -21.27%** |

---

## Bias hunt — what killed this strategy?
1. **The Friction Wall**: The gross edge per trade is only $+0.495\%$. After subtracting mandatory round-trip transaction costs ($0.500\%$), the net return per trade drops to $-0.005\%$.
2. **Subgroup Collapse (§8)**: Holdout Half B of names achieves a stable mean $z_{\text{paired}}$ of only $+0.68$ (0% pass rate) with a negative net return of $-0.099\%$.
3. **Survivorship Collapse**: Pre-2017 listings alone produce a stable mean $z_{\text{paired}}$ of $+0.91$ (0% pass rate) and negative net return ($-0.060\%$).
4. **Walk-Forward Regime Failure (§7)**: 3 of 5 chronological walk-forward folds produce negative day edges and negative paired $z$-scores (Fold 1: $z = -1.17$, Fold 4: $z = -0.56$, Fold 5 [most recent]: $z = -0.38$).
5. **Execution Fragility**: Fulfilling entry at the next open drops the net return further to $-0.369\%$ ($z = +0.43$).
6. **Economic Unviability**: In portfolio simulation across 20 slots, CAGR is negative ($-0.13\%$) and degrades to $-1.84\%$ at 2.0x costs.

---

## VERDICT
**REJECT** — Stable mean $z_{\text{paired}} = +1.22$ (0% pass rate across 20 control seeds), net return per trade is $-0.005\%$ after costs, fails holdout Half B ($z = +0.68$), fails pre-2017 survivorship ($z = +0.91$), dies in 3 of 5 walk-forward folds (most recent Fold 5 $z = -0.38$), and generates negative portfolio CAGR ($-0.13\%$).

Added a row to `REJECTED.md`? [x]

