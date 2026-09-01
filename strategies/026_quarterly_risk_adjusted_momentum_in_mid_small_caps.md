# Strategy 026 — Quarterly (63-Session) Risk-Adjusted Momentum in Mid/Small Caps

**Status:** **REJECTED** (2026-08-25) — Statistical selection edge is present (stable mean $z_{\text{paired}} = +3.24$, 100% pass), but **fails on portfolio economic resilience and regime stability**: loses to Buy-and-Hold at 1.5x costs (CAGR +16.85% vs +17.21% B&H), suffers severe underperformance in 2025 (-17.71% vs +0.44% B&H, -18.14% excess), and stalls in Fold 3 (2021-2023 $z_{\text{paired}} = +0.20$, 0% pass rate).  
**Date tested:** 2026-08-25  

---

## Hypothesis
In Indian markets, publicly traded companies release audited quarterly financial results on a ~63-trading-session cycle. 
Post-earnings revisions, institutional repositioning (mutual funds, FPIs), and analyst updates create multi-week quarterly drift.
Ranking liquid mid/small caps by 63-session (3-month) risk-adjusted momentum:
$$\text{Score}_{i,t} = \frac{\frac{\text{Close}_{i,t}}{\text{Close}_{i,t-63}} - 1.0}{\sigma_{60}(R_i)}$$
should isolate firms undergoing strong quarterly fundamental repricing. Holding top-decile names for 21 sessions (~1 calendar month) aims to harvest this drift while keeping round-trip turnover costs to ~12 rebalances per year.

## Checked against REJECTED.md and ADOPTED.md?
- [x] **Checked against REJECTED.md:**
  - 021 (rejected): 120d-ex-20d unadjusted raw momentum (crashed in 2024-2025).
  - 022 (rejected for swing): 12-month risk-adjusted momentum at 8-day hold (turnover friction destroyed edge).
  - 024 (provisional watch): 12-month risk-adjusted momentum at 21-day hold (held in watch pending forward test).
  - 025 (rejected): 12-month residual momentum (beta orthogonalization stripped high-beta winners).
  - 026 tests **3-month / 63-session (quarterly)** risk-adjusted momentum at a 21-session monthly holding horizon. Not previously in REJECTED.md.

## Rules (exact, unambiguous)
- **Universe:** Liquid NSE names not in the Nifty 50; 60-day median daily turnover $\ge \text{₹}25\text{ cr}$.
- **Signal (close of day t):** Rank liquid mid/small caps cross-sectionally by 63-session risk-adjusted momentum:
  $$\text{Score} = \frac{\text{change\_63d}}{\text{vol60}}$$
  Enter when `score` is in the **top decile** ($\ge 90\text{th percentile}$) that day.
- **Entry fill:** Same close (indicator signal computed from EOD prices). Next-open entry tested as a mandatory fragility check.
- **Exit:** Time exit at **21 trading sessions** (~1 calendar month), no ATR bracket.
- **Holding period:** 21 sessions.
- **Costs:** `charge_costs=True` (liquidity-tiered model, ~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode).

## Kill criteria — decided BEFORE running
REJECT if any of the following occur:
1. Stable mean $z_{\text{paired}}$ across 20 control seeds $< 2.0$ pooled **or** $< 2.0$ on the hold-out half B of names.
2. Net day edge $\le 0$ in any regime block (P1: 2016-2020, P2: 2021-2023, P3: 2024-2026).
3. **Survivorship:** Pre-2017 listings must clear stable mean $z_{\text{paired}} \ge 2.0$ **and** retain $\ge 60\%$ of pooled day edge.
4. **Decile Ladder:** Decile gradient must be monotonic from D10 down to D1.
5. **The Portfolio Tool Test:** A 20-slot equal-weight cash-constrained portfolio with 0.50% round-trip costs must beat buy-and-hold of the same universe on CAGR and risk-adjusted return (Sharpe), and must beat a random-selection portfolio.
6. **Execution / Control Fragility:** Dies against a volatility/beta-matched control or collapses under next-session entry fill.
7. **Walk-Forward Stability:** Walk-forward folds must remain consistently positive on paired $z$-score.

---

## Results (after running)

Command run:
```bash
python strategies/026_quarterly_risk_adjusted_momentum_in_mid_small_caps.py
```

### 1. Headline Engine Statistics (21-Session Hold)

| Metric | Strategy 026 (63d Mom) | Control (Random Entry) | Edge / Headline |
|---|---|---|---|
| Trades (non-overlapping) | 4,243 | 4,243 | — |
| Paired days | 1,893 | 1,893 | — |
| Gross avg return / trade | +2.318% | +1.464% | +0.854% |
| Avg round-trip cost | 0.500% | 0.500% | — |
| **NET avg return / trade** | **+1.818%** | **+0.964%** | **+0.854%** |
| Win rate | 53.0% | 49.2% | +3.8% |
| **naive z (edge_vs_control)** | +3.25 | — | (optimistic, not headline) |
| **DAY-CLUSTERED z_paired (seed 42)** | **+3.24** | — | day_edge: **+0.953%** |
| **POOLED Stable Mean z_paired (20 seeds)** | **+3.34** | (min +2.65, max +4.03) | **100% pass rate** |
| **Hold-out Half B Stable Mean z_paired** | **+2.76** | (min +1.43, max +3.83) | **90% pass rate** |

---

### 2. Holding Period Sensitivity ($\pm 1$ Step)

| Holding Period | Strategy Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge |
|---|---|---|---|---|---|
| **15 sessions** | 5,261 | 2,046 | +2.20 | 70% | +0.404% |
| **21 sessions (Baseline)** | 4,243 | 1,893 | **+3.34** | **100%** | **+0.953%** |
| **30 sessions** | 3,423 | 1,678 | +3.12 | 100% | +1.205% |
| **42 sessions** | 2,844 | 1,518 | +2.73 | 90% | +1.227% |

---

### 3. Regime Blocks & Survivorship

| Partition / Subgroup | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge |
|---|---|---|---|---|---|
| **P1 (2016-2020)** | 971 | 638 | +2.37 | 75% | +0.974% |
| **P2 (2021-2023)** | 1,327 | 604 | **+0.99** | **0%** | +0.246% |
| **P3 (2024-2026)** | 1,888 | 610 | +1.98 | 60% | +0.516% |
| **Pre-2017 Listings Only (462 names)** | 3,354 | 1,774 | +2.36 | 90% | +0.582% |
| Later Listings Only (167 names) | 889 | 534 | +2.37 | 70% | +1.655% |

_Note: Pre-2017 subgroup retains 61% of pooled day edge (clears kill threshold $\ge 60\%$)._

---

### 4. Decile Ladder Gradient

| Decile Rank | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|
| **D10 (Top Decile - Signal)** | 4,243 | 1,893 | **+3.34** | **+0.953%** | **+1.818%** |
| **D09** | 6,327 | 2,099 | +1.86 | +0.325% | +1.435% |
| **D08** | 7,588 | 2,154 | +0.73 | +0.107% | +1.316% |
| **D05 (Median)** | 8,797 | 2,227 | -2.20 | -0.446% | +0.739% |
| **D01 (Bottom Decile)** | 4,246 | 1,860 | -0.67 | -0.243% | +0.919% |

---

### 5. Controls, Fragility, & Walk-Forward Folds

- **Vol/Beta-MATCHED Control:** Stable mean $z_{\text{paired}} = \mathbf{+3.67}$ (100% pass), day edge = $+0.922\%$. Stronger than random control.
- **Next-Session Entry Fill:** Stable mean $z_{\text{paired}} = \mathbf{+3.02}$ (100% pass), day edge = $+0.791\%$.
- **Large Caps (Nifty 50):** Stable mean $z_{\text{paired}} = \mathbf{-1.05}$ (0% pass), day edge = $-0.556\%$. Factor fails in large caps.

#### Walk-Forward 5 Folds:
- **Fold 1 (2018-04-23 to 2019-12-30):** $z_{\text{paired}} = +1.27$, day_edge = $+0.599\%$
- **Fold 2 (2019-12-30 to 2021-08-25):** $z_{\text{paired}} = +1.85$, day_edge = $+1.044\%$
- **Fold 3 (2021-08-25 to 2023-04-25):** $z_{\text{paired}} = \mathbf{+0.20}$ (0% pass), day_edge = $+0.463\%$
- **Fold 4 (2023-04-25 to 2024-12-26):** $z_{\text{paired}} = +0.87$, day_edge = $+0.413\%$
- **Fold 5 (2024-12-26 to 2026-08-20):** $z_{\text{paired}} = +2.31$, day_edge = $+1.098\%$

---

### 6. The Portfolio Tool Test (20 Positions, Cash-Constrained, Costs Charged)

| Portfolio | CAGR | Max Drawdown | Sharpe Ratio | Final Equity |
|---|---|---|---|---|
| **Strategy 026 (63d Mom, h=21)** | **+20.25%** | **-43.5%** | **0.93** | **6.03x** |
| **Buy & Hold Benchmark Universe** | +17.21% | -54.3% | 0.87 | 4.70x |
| **Random Selection Control** | +7.01% | -63.5% | 0.43 | 1.94x |

#### Calendar Year Breakdown (Strategy vs Buy & Hold)
- **2016:** Strategy -3.20% vs B&H +4.19% (**-7.38%**)
- **2017:** Strategy +52.13% vs B&H +47.82% (**+4.31%**)
- **2018:** Strategy -14.77% vs B&H -16.54% (**+1.77%**)
- **2019:** Strategy +0.44% vs B&H -7.07% (**+7.50%**)
- **2020:** Strategy +32.84% vs B&H +22.20% (**+10.64%**)
- **2021:** Strategy +68.75% vs B&H +47.56% (**+21.18%**)
- **2022:** Strategy -0.11% vs B&H -2.05% (**+1.94%**)
- **2023:** Strategy +40.94% vs B&H +47.78% (**-6.83%**)
- **2024:** Strategy +34.81% vs B&H +27.95% (**+6.86%**)
- **2025:** Strategy -17.71% vs B&H +0.44% (**-18.14%**)  <-- Severe Drawdown / Whipsaw
- **2026:** Strategy +27.49% vs B&H +10.21% (**+17.28%**)

#### Cost Sensitivity (Round-Trip Friction)
- **1.0x Costs (0.50% RT):** CAGR **+20.25%** (beats B&H +17.21%)
- **1.5x Costs (0.75% RT):** CAGR **+16.85%** (**loses to B&H +17.21%**)
- **2.0x Costs (1.00% RT):** CAGR **+13.54%** (severely underperforms)

---

## Why it died (The Adversarial Autopsy)

1. **Cost Fragility:** At a 21-session holding period (~12 round trips/slot/year), friction accumulates rapidly (~6.0% annual drag at 0.50% RT; ~9.0% drag at 0.75% RT). At 1.5x costs (0.75% round-trip), the portfolio CAGR drops to +16.85%, trailing plain buy-and-hold (+17.21%). In liquid Indian mid/small caps where realistic spread + impact often reaches 0.70-0.90%, the economic excess vanishes.
2. **Severe 2025 Whipsaw Crash:** In 2025, when the mid/small universe was consolidating (+0.44% B&H), 3-month momentum experienced severe rotational whipsaw, crashing **-17.71%** (-18.14% relative to benchmark). 3-month momentum responds rapidly to short-term surges, buying near intermediate tops before quarterly reversals.
3. **Regime Lull in Fold 3 (2021-2023):** During 2021-2023, the paired $z$-score collapsed to $z_{\text{paired}} = +0.20$ (0% pass rate across control seeds), showing that selection skill was essentially absent during this extended 2-year market transition.

---

## VERDICT

**REJECT** — Day-clustered selection skill is statistically significant ($z_{\text{paired}} = +3.34$, 100% pass), but the strategy fails on economic robustness: it loses to Buy-and-Hold at 1.5x costs (+16.85% vs +17.21%), suffers a severe -18.14% excess crash in 2025 due to quarterly turnover whipsaw, and collapses in Fold 3 ($z_{\text{paired}} = +0.20$).

Added row to `REJECTED.md` via `python ledger.py reject`.
