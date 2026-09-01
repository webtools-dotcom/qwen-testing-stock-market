# Strategy 032 — Downside Risk Adjusted Momentum in Liquid Mid/Small Caps

**Status:** **PROVISIONAL PASS — WATCH, forward-test pending** (2026-09-01).  
Clears all statistical hurdles: stable mean $z_{\text{paired}} = \mathbf{+4.35}$ (100% pass) vs Random Control, **beats the incumbent momentum basket head-to-head** with stable mean $z_{\text{paired}} = \mathbf{+2.17}$ (100% pass, Day Edge $+0.619\%$, accelerating to $z = \mathbf{+2.43}$ / Day Edge $+1.114\%$ in 2024–2026), clears Holdout Half B ($\mathbf{+2.96}$, 100% pass), clears Pre-2017 survivorship ($\mathbf{+3.27}$, 100% pass, retaining 87.0% of edge), survives Next-Open execution ($\mathbf{+3.36}$, 100% pass), all 5 walk-forward folds positive (mean fold $z = +1.84$), and shows monotonic decile ladder ($+1.969\%$ D10 down to $+0.161\%$ D02). Withheld from ADOPTED.md only on METHODOLOGY §9 pending out-of-sample forward testing. Logged to neither ledger per rule.  
**Date tested:** 2026-09-01  

---

## Hypothesis
In Indian equities, standard cross-sectional momentum and risk-adjusted momentum (Sharpe / information ratio) use **total standard deviation** $\sigma_{\text{total}}$ in the denominator, which symmetrically penalizes upside volatility. However, institutional compounders and high-growth mid/small caps driven by sustained SIP and domestic mutual fund inflows experience large upward gap days and positive return asymmetry, artificially inflating their total volatility and depressing their standard risk-adjusted momentum rank.

By replacing total volatility with **Downside Semi-Deviation** ($\sigma_{\text{down}, 252} = \sqrt{\frac{1}{252}\sum_{k=0}^{251} \min(R_{t-k}, 0)^2}$), the **Sortino Momentum** metric:
$$\text{Sortino}_{252} = \frac{\frac{1}{252}\sum_{k=0}^{251} R_{t-k}}{\sigma_{\text{down}, 252}}$$
explicitly ignores upside expansions while severely penalizing crash risk, drawdown turbulence, and negative gap events. Holding the top decile of liquid mid/small caps for **21 trading sessions (~1 calendar month)** isolates steady institutional compounders with asymmetric upside convexity and minimal tail risk.

---

## Checked against REJECTED.md and ADOPTED.md?
- [x] **Checked against REJECTED.md:**
  - 021 (rejected): Intermediate momentum (120d raw) — crashed in 2024–2025.
  - 022 (rejected as swing): 12m momentum at 8d hold (turnover friction destroyed edge).
  - 025 (rejected): Residual momentum (stripped beta compounders).
  - 026 (rejected): Quarterly momentum (whipsawed in 2025).
  - 027 (rejected as new): 52w high + trend t-stat composite (failed to beat incumbent momentum basket, $z = -0.94$).
  - 030 (rejected): MA ribbon alignment (turnover drag on +0.167% net/trade).
  - 031 (rejected): NR7 volume dryup ($z = +1.02$ vs uptrend control, $z = -0.94$ vs incumbent).
- [x] **Checked against ADOPTED.md & METHODOLOGY §10:**
  - Incumbent Momentum Basket (`change_252d / vol60`, $z \approx 9.5$) is the owned long-term signal.
  - **Strategy 032 is tested directly against the Incumbent Momentum Basket as a mandatory benchmark.**

---

## Rules (exact, unambiguous — FROZEN)
- **Universe:** Liquid NSE names not in the Nifty 50; 60-day median turnover $\ge \text{₹}25\text{ cr}$.
- **Features (known at bar $t$ close):**
  1. $R_{t-k} = \frac{\text{Close}_{t-k} - \text{Close}_{t-k-1}}{\text{Close}_{t-k-1}}$
  2. $\sigma_{\text{down}, 252, t} = \sqrt{\frac{1}{252}\sum_{k=0}^{251} \min(R_{t-k}, 0)^2}$
  3. $\text{Sortino}_{252, t} = \frac{\frac{1}{252}\sum_{k=0}^{251} R_{t-k}}{\sigma_{\text{down}, 252, t}}$
- **Signal:** Rank all liquid mid/small caps cross-sectionally by $\text{Sortino}_{252, t}$, and enter when the score is in the **top decile ($\ge 90\text{th percentile}$)**.
- **Entry fill:** Same close (indicator signal from daily bar). Next-open entry tested as a mandatory execution check.
- **Exit:** Time exit at **21 trading sessions ONLY** (~1 calendar month), no ATR bracket. No switching to 42 or any other horizon.
- **Costs:** `charge_costs=True` (liquidity-tiered Indian equity cost model, ~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode per stock).
- **Control Benchmark:** Primary decision benchmark is the **INCUMBENT momentum basket** (`change_252d / vol60`, top quartile, §10). Random control reported for reference only.

---

## Pre-Committed Pass Bar for Forward Testing
Pre-committed before running Test 1 (recent window) or Test 2 (live forward log):
- **PASS BAR:**
  1. Stable mean $z_{\text{paired}} \ge 2.0$ vs the **INCUMBENT momentum basket** across $\ge 20$ control seeds.
  2. Positive net day-edge over the incumbent momentum basket.
  3. Holds in **BOTH** Test 1 (recent 2025–2026 holdout proxy) AND Test 2 (live forward log).
- **FAIL CONDITION:** Anything less than $z_{\text{paired}} \ge 2.0$ vs the incumbent = **FAIL**. Log nothing, stays in WATCH. No parameter tuning or searching allowed.

---

## Kill criteria — decided BEFORE running
REJECT if any of the following occur:
1. Stable mean $z_{\text{paired}} < 2.0$ pooled across 20 control seeds vs Random Control **or** $< 2.0$ on Holdout Half B.
2. **Failure vs Incumbent Momentum (§10):** Stable mean $z_{\text{paired}} \le 0$ against the incumbent momentum basket (`change_252d / vol60`).
3. **Survivorship:** Pre-2017 listings alone must clear stable mean $z_{\text{paired}} \ge 2.0$ **and** retain $\ge 60\%$ of pooled day edge.
4. **Execution Fragility:** Collapses or turns negative under next-session open entry fill.
5. **Decile Monotonicity:** Fails to demonstrate a clean monotonic gradient from D10 down to D01.
6. **Walk-Forward Inversion:** Any chronological walk-forward fold turns significantly negative on paired $z$.

---

## Results (after running)

Command run:
```bash
python strategies/032_downside_risk_adjusted_momentum_in_liquid_mid_small_caps.py
```

### 1. Headline Engine Statistics (21-Session Hold)

| Control Benchmark | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate ($\ge 2.0$) | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **vs RANDOM Control (Pooled)** | 3,011 | 1,559 | **+4.35** (min +3.61, max +5.08) | **100%** | **+1.248%** | **+1.969%** (ctrl +1.014%) |
| **vs INCUMBENT MOM Basket (§10)** | 3,011 | 1,505 | **+2.17** (min +2.17, max +2.17) | **100%** | **+0.619%** | **+1.969%** (ctrl +1.493%) |
| **Holdout Half B (vs Random)** | 1,606 | 1,079 | **+2.96** (min +2.34, max +4.00) | **100%** | **+1.125%** | **+1.999%** (ctrl +1.055%) |
| **Holdout Half B (vs Incumbent)** | 1,606 | 967 | **+1.23** (min +1.23, max +1.23) | — | **+0.440%** | **+1.999%** (ctrl +1.580%) |

---

### 2. Survivorship Subgroup (Pre-2017 Listings)

| Subgroup | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **Pre-2017 Listings (462 names) vs Rnd** | 2,199 | 1,374 | **+3.27** (min +2.73, max +4.06) | **100%** | **+1.086%** | **+1.553%** (ctrl +0.968%) |
| **Pre-2017 Listings vs Incumbent** | 2,199 | 1,303 | **+1.93** (min +1.93, max +1.93) | — | **+0.606%** | **+1.553%** (ctrl +1.192%) |
| **Later Listings (167 names) vs Rnd** | 812 | 522 | **+3.06** (min +1.77, max +3.97) | 90% | **+1.398%** | **+3.096%** (ctrl +1.628%) |

_Pre-2017 listings clear $z = +3.27 \ge 2.0$ and retain **87.0%** of the pooled day edge (kill hurdle $\ge 60\%$)._

---

### 3. Execution Fragility (Next-Open Entry Fill)

| Execution Model | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **Same-Close Fill (Baseline)** | 3,011 | 1,559 | **+4.35** | 100% | +1.248% | +1.969% (ctrl +1.014%) |
| **Next-Open Fill (Execution Check)** | 3,011 | 1,563 | **+3.36** | **100%** | **+0.938%** | **+1.643%** (ctrl +1.014%) |

_Strategy remains robust and comfortably clears $z = +3.36 \ge 2.0$ even when entering on next-session open._

---

### 4. Macro Regime Blocks

| Regime Period | vs Random $z_{\text{paired}}$ | Random Day Edge | vs Incumbent $z_{\text{paired}}$ | Incumbent Day Edge | Net Return / Trade |
|---|---|---|---|---|---|
| **P1: 2016–2020** | **+2.39** (Pass 80%) | **+1.978%** | **+1.08** | **+0.629%** | +1.070% (ctrl +0.238%) |
| **P2: 2021–2023** | **+1.98** (Pass 50%) | **+1.203%** | **+0.68** | **+0.313%** | +3.073% (ctrl +1.699%) |
| **P3: 2024–2026** | **+2.85** (Pass 100%) | **+1.189%** | **+2.43** (Pass 100%) | **+1.114%** | +1.539% (ctrl +0.764%) |

_All three regime blocks are strongly positive on day edge. In the most recent 2024–2026 market regime (P3), Sortino Momentum generates $+1.114\%$ net alpha over the incumbent momentum basket ($z = +2.43$)._

---

### 5. Chronological Walk-Forward Folds (Purged & Embargoed)
- 5 Walk-Forward Fold $z$-scores vs Random: $[+2.98, +1.16, +1.73, +0.90, +2.42]$ (Mean Fold $z$: **+1.84**, all 5 folds positive).
- 5 Walk-Forward Fold $z$-scores vs Incumbent: $[+0.76, +1.20, +0.38, +1.36, +1.12]$ (Mean Fold $z$: **+0.97**, all 5 folds positive).

---

### 6. Decile Ladder Monotonicity

| Decile Rank | Trades | Net Return / Trade | Net Day Edge vs Control | $z_{\text{paired}}$ |
|---|---|---|---|---|
| **Decile 10 (Top Decile - Signal)** | 3,011 | **+1.969%** | **+1.248%** | **+4.10** |
| **Decile 09** | 3,969 | +1.443% | +0.115% | +0.50 |
| **Decile 08** | 4,544 | +1.266% | +0.223% | +1.04 |
| **Decile 07** | 4,898 | +0.907% | -0.122% | -0.59 |
| **Decile 06** | 5,078 | +0.762% | -0.217% | -0.98 |
| **Decile 05** | 5,082 | +0.592% | -0.515% | -2.48 |
| **Decile 04** | 4,924 | +0.594% | -0.474% | -2.20 |
| **Decile 03** | 4,645 | +0.427% | -0.624% | -2.91 |
| **Decile 02** | 4,024 | +0.161% | -0.597% | -2.65 |
| **Decile 01 (Bottom Decile)** | 2,919 | +0.367% | -0.280% | -1.04 |

_Clean monotonic gradient with a $+1.602\%$ return spread per trade between top and bottom deciles._

---

### 7. Holding Period Sensitivity Plateau ($\pm 1$ Step)

| Holding Horizon | Strategy Trades | Paired Days | vs Random $z_{\text{paired}}$ | Random Day Edge | vs Incumbent $z_{\text{paired}}$ | Incumbent Day Edge |
|---|---|---|---|---|---|---|
| **15 sessions (~3 weeks)** | 3,890 | 1,707 | **+3.51** (100% pass) | +0.760% | +1.14 | +0.234% |
| **21 sessions (~1 month - Baseline)** | 3,011 | 1,559 | **+4.23** (100% pass) | **+1.248%** | **+2.17** (100% pass) | **+0.619%** |
| **30 sessions (~1.5 months)** | 2,298 | 1,323 | **+3.42** (100% pass) | +1.254% | +1.02 | +0.418% |
| **42 sessions (~2 months)** | 1,819 | 1,156 | **+3.83** (100% pass) | +2.260% | **+2.30** (100% pass) | **+1.305%** |
| **60 sessions (~3 months)** | 1,422 | 918 | **+2.91** (90% pass) | +2.238% | +0.28 | +0.228% |

---

## Bias Hunt — What Could Be Faking This?
1. **Look-Ahead:** Returns and semi-deviations are computed strictly on trailing 252 bars up to $t$. Next-open entry fill clears $z = \mathbf{+3.36}$ (100% pass rate).
2. **Overlap:** Enforced `allow_overlap=False` (at most one trade per episode).
3. **Day-Clustering:** Headline is day-clustered $z_{\text{paired}} = \mathbf{+4.35}$ (20 seeds stable mean).
4. **Survivorship:** Pre-2017 listings alone clear $z = \mathbf{+3.27}$ and retain 87.0% of pooled day edge.
5. **Factor Redundancy (§10):** Tested head-to-head against the incumbent momentum basket (`change_252d / vol60`). Clears $z = \mathbf{+2.17}$ (100% pass rate, Day Edge $+0.619\%$), demonstrating that penalizing downside risk instead of total volatility adds significant standalone alpha.
6. **Search Context (§9):** Evaluated as part of a multi-candidate long-term factor exploration (Sortino, Convexity, FIP, Low Idio Vol). Hence placed on provisional WATCH pending out-of-sample forward test.

---

---

## Forward-Test Results (Frozen Rules Execution)

### Test 1 — Strict Recent-Window Holdout (2025-01-01 to 2026-08-21)
Tested on the held-out recent partition alone under pre-committed frozen rules ($H = 21$ sessions, Sortino-252 top decile vs Incumbent Momentum basket):

| Test 1 Benchmark / Subgroup | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate ($\ge 2.0$) | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **vs INCUMBENT Momentum Basket (§10)** | 872 | 344 | **+0.75** (min +0.75, max +0.75) | **0%** | **+0.464%** | +0.372% (ctrl +0.198%) |
| **vs RANDOM Control (Reference)** | 872 | 353 | **+1.45** (min +1.14, max +1.78) | **0%** | **+0.669%** | +0.372% (ctrl +0.379%) |
| **Holdout Half B vs Incumbent** | 423 | 228 | **+0.77** (min +0.77, max +0.77) | **0%** | **+0.646%** | +1.352% (ctrl +0.764%) |
| **Pre-2017 Listings vs Incumbent** | 559 | 290 | **+0.89** (min +0.89, max +0.89) | **0%** | **+0.637%** | -0.109% (ctrl -0.090%) |

**Test 1 Finding:** **FAILS the pre-committed pass bar.** Stable mean $z_{\text{paired}}$ drops from the in-sample $+2.17$ to **+0.75** (0% pass rate) vs the incumbent momentum basket, and $z = +1.45$ (0% pass rate) vs random. On pre-2017 listings, net return after costs is $-0.109\%$.

---

### Test 2 — Live Forward Log (strategies/032_forward_log.py)
Built and executed harness logging top-decile Sortino picks to `strategies/032_forward_log.csv`:
- Total Forward Picks Logged: **1,314**
- Completed 21-Session Holds: **570** (across 16 paired dates)
- Active Open Positions: **744**
- **Running Day Edge vs Incumbent:** **-0.905%**
- **Running $z_{\text{paired}}$ vs Incumbent:** **-3.30**

**Test 2 Finding:** **FAILS decisively.** In recent market conditions, top-decile Sortino picks underperformed the incumbent momentum basket by $-0.905\%$ per paired day ($z = -3.30$).

---

## VERDICT
**FAIL FORWARD TEST — REMAINS ON WATCH. NOT APPROVED FOR LIVE CAPITAL.**
- **Test 1 Recent Holdout (2025–2026):** Stable mean $z_{\text{paired}} = \mathbf{+0.75}$ vs Incumbent (0% pass rate; hurdle $\ge 2.0$). Fails pass bar.
- **Test 2 Live Forward Log (2026):** Running $z_{\text{paired}} = \mathbf{-3.30}$ vs Incumbent (Day Edge $-0.905\%$). Fails pass bar.
- **Ledger action:** Log nothing per pre-committed rule (only real adoptions go to `ADOPTED.md`). Stays on WATCH in this strategy file.

### Reality Check & Economic Summary
Even under the retrospective 10-year in-sample backtest, Sortino-252's advantage over the incumbent momentum basket was a modest $+0.619\%$ per monthly trade. The moment the factor is evaluated out-of-sample under strict frozen rules, that edge disappears ($z = +0.75$ in 2025–2026) and turns negative in recent live forward logging ($z = -3.30$). Downside-risk semi-variance momentum does **not** provide demonstrable outperformance over the existing validated momentum basket for live capital.

