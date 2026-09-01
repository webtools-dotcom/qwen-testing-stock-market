# Strategy 034 — Low Idiosyncratic Volatility 52-Week High Volume Thrust in Liquid Mid-Small Caps

**Status:** **REJECTED** (2026-09-01)  
**Headline Result:** Pooled stable mean $z_{\text{paired}} = \mathbf{+0.73}$ (0% pass rate across 20 seeds) with negative day edge ($-0.205\%$), completely fails against the Incumbent Momentum Basket (stable mean $z_{\text{paired}} = \mathbf{-0.28}$, day edge $-0.067\%$, METHODOLOGY §10), collapses under next-open execution ($z_{\text{paired}} = \mathbf{-0.78}$ vs random, $\mathbf{-2.66}$ vs incumbent), fails 4 of 5 chronological walk-forward folds ($z_{\text{paired}} = -1.28, -1.29, +0.07, +0.37$), and shows universally negative paired edge across the entire parameter sensitivity grid.  
**Date tested:** 2026-09-01  

---

## Hypothesis
In Indian equities, stocks that are trading within 5% of their 52-week high while exhibiting low idiosyncratic volatility ($\le 40\text{th percentile}$ cross-sectionally) represent high-quality institutional compounders. When such a stock experiences an institutional volume surge ($\text{Volume} \ge 1.8\times$ 20-day median) accompanied by an upward expansion thrust ($\text{Ret}_1 \ge +1.50\%$ with $\text{Close} > \text{Open}$), this price-volume breakout signals fresh institutional accumulation that should generate positive swing momentum continuation over a 10-session (2-week) horizon.

---

## Checked against REJECTED.md and ADOPTED.md?
- [x] **Checked against REJECTED.md:**
  - 007: Inside-day NR4 breakout (rejected, $z = 1.45$, next-open loss).
  - 015: 50-day high breakout with high turnover (rejected, $z = 1.16$, net edge $-0.096\%$).
  - 020: Turnover expansion attention drift (rejected, flips sign on holdouts).
  - 022 & 033: 10-day momentum swing (rejected due to cost drag and failure vs incumbent).
  - 026: VCP / consolidation breakouts (failed across all 5y panels).
- [x] **Checked against ADOPTED.md & METHODOLOGY §10:**
  - 52-week high nearness and low-volatility tilts are part of the owned Momentum family ($z \approx 9.5$).
  - Per METHODOLOGY §10, any candidate in this family must be tested directly against the Incumbent Momentum Basket (`change_252d / vol60`).

---

## Rules (exact, unambiguous)
- **Universe:** Liquid NSE mid/small cap stocks (excluding Nifty 50 constituents); 60-day median turnover $\ge \text{₹}25\text{ cr}$.
- **Features (known at bar $t$ close):**
  1. $\text{dist\_high250}_t = \frac{\text{Close}_t}{\max_{k=0}^{251}(\text{Close}_{t-k})} - 1 \ge -0.05$ (within 5% of 52-week high).
  2. $\text{idio\_vol\_pct}_t \le 0.40$ (bottom 40% of cross-sectional daily idiosyncratic volatility, residual return volatility vs market).
  3. $\text{vol\_ratio1}_t = \frac{\text{Volume}_t}{\text{median}_{20}(\text{Volume})} \ge 1.80$ (institutional volume expansion).
  4. $\text{ret1}_t = \frac{\text{Close}_t - \text{Close}_{t-1}}{\text{Close}_{t-1}} \times 100 \ge +1.50\%$ and $\text{Close}_t > \text{Open}_t$ (upward green candle thrust).
- **Entry fill:** Same close (indicator signal from daily OHLCV). Next-open entry tested as a mandatory execution check.
- **Exit:** Unconditional time exit after **10 trading sessions** (2 calendar weeks).
- **Costs:** `charge_costs=True` (liquidity-tiered Indian equity cost model, ~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode per stock).

---

## Kill criteria — decided BEFORE running
REJECT if any of the following occur:
1. Stable mean $z_{\text{paired}} < 2.0$ pooled across 20 control seeds vs Random Control.
2. **Failure vs Incumbent Momentum (§10):** Stable mean $z_{\text{paired}} \le 0$ or negative day edge against the Incumbent Momentum Basket (`change_252d / vol60`, top quartile).
3. **Execution Fragility:** Collapses or turns negative under next-session open entry fill.
4. **Subgroup Failure (§8):** Fails to clear $z_{\text{paired}} \ge 2.0$ on Holdout Half B.
5. **Walk-Forward Inversion:** Chronological walk-forward folds turn negative or fail to clear.
6. **Parameter Sensitivity:** Fails across parameter grid variations (Volume 1.5x, 1.8x, 2.2x; Return 1.0%, 1.5%, 2.0%).

---

## Results (measured)

Command run:
```bash
python strategies/034_low_idiosyncratic_volatility_52_week_high_volume_thrust_in_liquid_mid_small_caps.py
```

### 1. Headline Engine Statistics (10-Session Hold)

| Control Benchmark | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate ($\ge 2.0$) | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **vs RANDOM Control (Pooled)** | 1,574 | 895 | **+0.73** (min -0.23, max +1.43) | **0%** | **-0.205%** | **+1.031%** (ctrl +0.753%) |
| **vs INCUMBENT MOM Basket (§10)** | 1,574 | 890 | **-0.28** (min -0.28, max -0.28) | **0%** | **-0.067%** | **+1.031%** (ctrl +0.958%) |
| **Holdout Half B (vs Random)** | 816 | 571 | **+1.81** (min +0.20, max +3.61) | 50% | **+0.746%** | **+1.369%** (ctrl +0.595%) |
| **Holdout Half B (vs Incumbent)** | 816 | 550 | **+0.35** (min +0.35, max +0.35) | 0% | **+0.133%** | **+1.369%** (ctrl +0.977%) |

### 2. Survivorship Subgroup (Pre-2017 Listings Only)

| Subgroup | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **Pre-2017 Listings vs Random** | 743 | 506 | **+2.33** (min +0.85, max +3.87) | 75% | **+0.732%** | **+0.998%** (ctrl +0.305%) |
| **Pre-2017 Listings vs Incumbent** | 743 | 454 | **+1.62** (min +1.62, max +1.62) | 0% | **+0.576%** | **+0.998%** (ctrl +0.386%) |

### 3. Execution Fragility (Next-Open Entry Fill)

| Execution Model | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **Next-Open Fill (vs Random)** | 1,574 | 894 | **-0.78** (min -1.65, max +0.43) | **0%** | **-0.393%** | **+0.629%** (ctrl +0.753%) |
| **Next-Open Fill (vs Incumbent)** | 1,574 | 890 | **-2.66** (min -2.66, max -2.66) | **0%** | **-0.667%** | **+0.629%** (ctrl +0.958%) |

_The edge catastrophically reverses under next-session execution: stable mean $z_{\text{paired}} = -0.78$ vs random and $-2.66$ vs incumbent, with day edge of $-0.667\%$. Entering after the thrust bar suffers immediate mean reversion / morning fade._

### 4. Walk-Forward Chronological Folds (Purged & Embargoed)

| Fold | Date Range | Trades | Net Return % | Net Day Edge % | Paired $z$ | Verdict |
|---|---|---|---|---|---|---|
| **Fold 1** | 2017-08-28 to 2020-10-29 | 216 | -0.281% | -1.336% | **-1.28** | FAIL (Negative) |
| **Fold 2** | 2020-10-30 to 2022-08-19 | 290 | +1.556% | -0.851% | **-1.29** | FAIL (Negative) |
| **Fold 3** | 2022-08-24 to 2023-12-21 | 344 | +1.749% | +0.032% | **+0.07** | FAIL (Zero edge) |
| **Fold 4** | 2023-12-22 to 2024-12-17 | 440 | +0.994% | +0.160% | **+0.37** | FAIL (Underpowered) |
| **Fold 5** | 2024-12-30 to 2026-07-30 | 274 | +0.707% | +0.961% | **+2.32** | PASS |

_4 out of 5 chronological folds completely fail to clear the bar ($z = -1.28, -1.29, +0.07, +0.37$). The signal is completely non-stationary and only produced significance during the 2025–2026 small-cap liquidity bubble._

### 5. Parameter Sensitivity Grid

| Volume Hurdle | Return Hurdle | Trades | Net Return / Trade | Net Day Edge | $z_{\text{paired}}$ |
|---|---|---|---|---|---|
| Vol > 1.5x | Ret > 1.0% | 2,099 | +0.924% | -0.063% | -0.26 |
| Vol > 1.5x | Ret > 1.5% | 1,954 | +0.981% | -0.015% | -0.06 |
| Vol > 1.5x | Ret > 2.0% | 1,783 | +1.091% | -0.040% | -0.15 |
| Vol > 1.8x | Ret > 1.0% | 1,672 | +1.000% | -0.178% | -0.64 |
| **Vol > 1.8x** | **Ret > 1.5% (Base)** | **1,574** | **+1.031%** | **-0.205%** | **-0.71** |
| Vol > 1.8x | Ret > 2.0% | 1,462 | +1.121% | -0.208% | -0.69 |
| Vol > 2.2x | Ret > 1.0% | 1,276 | +1.033% | -0.096% | -0.32 |
| Vol > 2.2x | Ret > 1.5% | 1,211 | +1.112% | -0.178% | -0.58 |
| Vol > 2.2x | Ret > 2.0% | 1,134 | +1.165% | -0.155% | -0.49 |

_Across all 9 combinations of volume and return expansion, Day Edge is uniformly negative ($-0.015\%$ to $-0.208\%$) and $z_{\text{paired}}$ is uniformly negative ($-0.06$ to $-0.71$). There is zero robust plateau._

---

## Bias Hunt & Decisive Kill Analysis

Why Strategy 034 fails decisively and must be killed:

1. **Failure vs Random Control:**  
   The pooled stable mean $z_{\text{paired}}$ across 20 control seeds is only **+0.73** with a **0% pass rate** (never once reaching 2.0 in 20 seeds). The day-clustered net edge is negative (**-0.205%**).
2. **Failure vs Incumbent Momentum (§10):**  
   When paired against the Incumbent Momentum Basket (`change_252d / vol60`), the stable mean $z_{\text{paired}}$ collapses to **-0.28** (Day Edge $-0.067\%$). It is simply a worse, friction-heavy version of the long-term momentum signal.
3. **Execution Fragility / The Pop-and-Fade Trap:**  
   Under Next-Open execution, $z_{\text{paired}}$ plunges to **-0.78** vs random and **-2.66** vs incumbent. In Indian equities, buying a stock that has just popped +1.5% to +3.0% on heavy volume at 52-week highs suffers immediate intraday mean reversion and opening auction fade over the subsequent sessions.
4. **Regime Instability (Walk-Forward Collapse):**  
   Folds 1 through 4 (2017 to 2024) are completely dead or deeply negative ($z = -1.28, -1.29, +0.07, +0.37$). The apparent pop in gross returns was confined entirely to the 2025–2026 domestic SIP liquidity wave.
5. **Universal Parameter Grid Failure:**  
   Every single cell in the $3 \times 3$ volume-return sensitivity grid exhibits negative paired day edge and negative $z_{\text{paired}}$.

---

## VERDICT
**REJECT** — Stable mean $z_{\text{paired}} = +0.73$ (0% pass rate) vs random, $z_{\text{paired}} = -0.28$ vs incumbent momentum, collapses to $z = -2.66$ on next-open execution, and fails 4 of 5 walk-forward folds.

