# Strategy 033 — Sortino Momentum Top Decile 10-Session Swing in Mid-Small Caps

**Status:** **REJECTED** (2026-09-01)  
**Headline Result:** Pooled stable mean $z_{\text{paired}} = \mathbf{+3.69}$ (100% pass rate) vs Random Control, but **fails vs Incumbent Momentum Basket** (stable mean $z_{\text{paired}} = \mathbf{+0.97}$, collapsing to $z = \mathbf{+0.07}$ under next-open execution per METHODOLOGY §10) and **fails economic portfolio reality** (CAGR $+4.37\%$ vs $+22.10\%$ Buy & Hold, collapsing to $-6.94\%$ at 1.5x costs due to $32.5\%/\text{year}$ turnover drag on a 10-session hold).  
**Date tested:** 2026-09-01  

---

## Hypothesis
In Indian mid- and small-cap stocks, downside semi-variance ($\sigma_{\text{down}, 252}$) isolates crash risk and negative asymmetry without penalizing upside momentum expansions. Stocks ranking in the top decile ($\ge 90\text{th percentile}$) of 252-day Downside Risk-Adjusted Momentum (Sortino Ratio) represent high-quality compounders with asymmetric upside drift.

A swing trader holding these names for **10 trading sessions (2 calendar weeks)** aims to harvest short-term institutional alpha while avoiding the long-term drawdown drag of passive index exposure.

---

## Checked against REJECTED.md and ADOPTED.md?
- [x] **Checked against REJECTED.md:**
  - 022 (rejected): Risk-adjusted 12m momentum at 8-day hold (failed on portfolio cost economics: 14%/yr turnover drag on thin edge).
  - 027 (rejected as new): 52w high trend consistency composite (failed to beat incumbent momentum basket head-to-head, $z = -0.94$).
  - 028, 029, 031: Short-term pullback and absorption swing strategies in trend leaders (all failed Half B or day-clustering).
- [x] **Checked against ADOPTED.md & METHODOLOGY §10:**
  - Incumbent Momentum Basket (`change_252d / vol60`, $z \approx 9.5$) is the owned long-term signal.
  - Per METHODOLOGY §10, any momentum-family idea must be tested directly against the Incumbent Momentum Basket as a mandatory benchmark.

---

## Rules (exact, unambiguous)
- **Universe:** Liquid NSE mid/small cap stocks (excluding Nifty 50 constituents); 60-day median turnover $\ge \text{₹}25\text{ cr}$.
- **Feature (known at bar $t$ close):**
  $$\text{Sortino}_{252, t} = \frac{\frac{1}{252}\sum_{k=0}^{251} R_{t-k}}{\sqrt{\frac{1}{252}\sum_{k=0}^{251} \min(R_{t-k}, 0)^2}}$$
- **Signal:** Cross-sectional daily percentile rank $\ge 0.90$ (top decile) among all liquid mid/small cap stocks.
- **Entry fill:** Same close (indicator signal from daily OHLCV). Next-open entry tested as a mandatory execution check.
- **Exit:** Unconditional time exit after **10 trading sessions** (2 calendar weeks), no ATR bracket.
- **Costs:** `charge_costs=True` (liquidity-tiered Indian equity cost model, ~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode per stock).

---

## Kill criteria — decided BEFORE running
REJECT if any of the following occur:
1. Stable mean $z_{\text{paired}} < 2.0$ pooled across 20 control seeds vs Random Control.
2. **Subgroup failure (§8):** Holdout Half B stable mean $z_{\text{paired}} < 2.0$.
3. **Failure vs Incumbent Momentum (§10):** Stable mean $z_{\text{paired}} \le 0$ or fails to demonstrate statistically significant edge over the incumbent momentum basket (`change_252d / vol60`).
4. **Survivorship Failure:** Pre-2017 listings alone fail stable mean $z_{\text{paired}} \ge 2.0$.
5. **Execution Fragility:** Collapses or turns negative under next-session open entry fill.
6. **Portfolio Drag Failure:** In a 20-slot portfolio simulation, CAGR lags Buy & Hold of the universe or turns negative at 1.5x costs ($0.75\%$ round trip).

---

## Results (measured)

Command run:
```bash
python strategies/033_sortino_momentum_top_decile_10_session_swing_in_mid_small_caps.py
```

### 1. Headline Engine Statistics (10-Session Hold)

| Control Benchmark | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate ($\ge 2.0$) | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **vs RANDOM Control (Pooled)** | 5,333 | 1,937 | **+3.69** (min +2.88, max +4.29) | **100%** | **+0.651%** | **+0.711%** (ctrl +0.191%) |
| **vs INCUMBENT MOM Basket (§10)** | 5,333 | 1,931 | **+0.97** (min +0.97, max +0.97) | **0%** | **+0.147%** | **+0.711%** (ctrl +0.476%) |
| **Holdout Half B (vs Random)** | 2,851 | 1,550 | **+2.73** (min +2.20, max +3.51) | **100%** | **+0.396%** | **+0.709%** (ctrl +0.290%) |
| **Holdout Half B (vs Incumbent)** | 2,851 | 1,492 | **+1.24** (min +1.24, max +1.24) | — | **+0.227%** | **+0.709%** (ctrl +0.506%) |

### 2. Survivorship Subgroup (Pre-2017 Listings Only)

| Subgroup | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **Pre-2017 Listings (462 names) vs Rnd** | 3,887 | 1,798 | **+2.41** (min +1.78, max +3.14) | **85%** | **+0.406%** | **+0.424%** (ctrl +0.187%) |
| **Pre-2017 Listings vs Incumbent** | 3,887 | 1,773 | **+0.59** (min +0.59, max +0.59) | 0% | **+0.094%** | **+0.424%** (ctrl +0.339%) |

### 3. Execution Fragility (Next-Open Entry Fill)

| Execution Model | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **Same-Close Fill (Baseline vs Rnd)** | 5,333 | 1,937 | **+3.69** | 100% | +0.651% | +0.711% (ctrl +0.191%) |
| **Next-Open Fill (vs Random)** | 5,333 | 1,937 | **+2.50** | **85%** | **+0.452%** | **+0.505%** (ctrl +0.191%) |
| **Next-Open Fill (vs Incumbent)** | 5,333 | 1,920 | **+0.07** | **0%** | **+0.013%** | **+0.505%** (ctrl +0.476%) |

### 4. Walk-Forward Chronological Folds (Purged & Embargoed)
- 5 Walk-Forward Fold $z$-scores: `[+3.23, +0.57, +2.24, +2.25, +0.63]`, Mean Fold $z = \mathbf{+1.79}$. All 5 folds positive.

### 5. Portfolio Simulation Stress Test (20 Slots, 10-Session Rebalance)

| Cost Multiplier | Round-Trip Cost % | Strategy CAGR | Strategy Sharpe | Max Drawdown | Total Trades | Benchmark B&H CAGR |
|---|---|---|---|---|---|---|
| **1.0x Costs** | 0.50% | **+4.37%** | 0.30 | -50.03% | 7,864 | **+22.10%** (Sharpe 1.15) |
| **1.5x Costs** | 0.75% | **-6.94%** | -0.19 | -73.76% | 7,864 | +22.10% |
| **2.0x Costs** | 1.00% | **-16.88%** | -0.70 | -89.25% | 7,864 | +22.10% |

---

## The Decisive Kill Analysis

Why Strategy 033 fails and must be REJECTED:

1. **Failure to Beat Incumbent Momentum (§10):**  
   Against a naive random control, Sortino Top Decile looks stellar (stable mean $z_{\text{paired}} = +3.69$, 100% pass rate). But the momentum factor family is already owned in this repository. When tested head-to-head against the Incumbent Momentum Basket (`change_252d / vol60`), the stable mean $z_{\text{paired}}$ collapses to **+0.97** (0% pass rate) on same-close fills, and completely evaporates to **+0.07** under Next-Open execution. It does not add statistically significant alpha over what the platform already runs.

2. **The 6–10 Day Turnover Cost Drag Wall (Economic Infeasibility):**  
   Rebalancing a 20-slot portfolio every 10 sessions generates **7,864 trades** across 10 years (~65 round trips per slot per year). In Indian equities, round-trip costs (STT, brokerage, stamp duty, GST, exchange fees, bid-ask slippage) average $0.50\%$. 
   $$65 \text{ round trips} \times 0.50\% = \mathbf{32.5\%\text{ per year in transaction friction!}}$$
   Against a net edge of $+0.711\%$ per trade, this colossal friction drag crushes portfolio CAGR to **+4.37%** (Sharpe 0.30) compared to **+22.10%** (Sharpe 1.15) for simply buy-and-holding the same universe. At 1.5x costs ($0.75\%$), CAGR flips to **-6.94%**, and at 2x costs collapses to **-16.88%**.

---

## VERDICT
**REJECT** — While the selection edge clears random control ($z = +3.69$ pooled, $+2.73$ Half B, $+2.41$ Pre-2017), it fails head-to-head vs the Incumbent Momentum Basket ($z = +0.97$, next-open $z = +0.07$ per METHODOLOGY §10) and fatally fails portfolio economic reality (+4.37% CAGR vs +22.10% Buy & Hold, collapsing to -6.94% at 1.5x costs due to 32.5%/year turnover friction drag on a 10-session hold).

