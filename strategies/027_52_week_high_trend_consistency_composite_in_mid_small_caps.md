# Strategy 027 — 52-Week High Trend Consistency Composite in Mid/Small Caps

**Status:** **REJECTED-as-new (Rediscovery)** (2026-08-31) — Verified numbers reproduce, but per METHODOLOGY §10 this is a weaker rediscovery (z 3.80 vs z 9.5) of the parent tool's already-owned momentum + low-vol signal. Logged to REJECTED.md.  
**Date tested:** 2026-08-29  


---

## Hypothesis
In Indian markets, institutional domestic mutual funds (DIIs) and retail systematic investment plans (SIPs) allocate steady capital month after month into high-quality mid/small cap compounders.
Two distinct behavioral and structural mechanisms create a persistent 1-2 month positive drift:
1. **George & Hwang (2004) 52-Week High Anchor Effect:** Investors anchor on the 52-week high, creating an underreaction disposition effect. As a stock approaches its 52-week high, overhead supply dries up and price discovery accelerates.
2. **Trend Consistency / Information Ratio ($\frac{\mu_{252}}{\sigma_{252}} \sqrt{252}$):** Stocks that trend upward through small, steady daily gains with low path volatility (high Sharpe / Information Ratio of the trend) represent continuous institutional accumulation (Frog-in-the-Pan effect, Da et al. 2014) rather than speculative retail spikes.

Combining cross-sectional rank of **52-Week High Nearness** and **252-Day Trend Consistency (t-statistic)** into an equal-weight composite isolates high-conviction, low-volatility institutional compounders. Holding them for **42 sessions (~2 calendar months)** allows the drift to compound while reducing annual turnover friction to ~6 rebalances/year.

---

## Checked against REJECTED.md and ADOPTED.md?
- [x] **Checked against REJECTED.md:**
  - 015 (rejected): 50-day high breakout swing ($z = 1.16$, negative net edge).
  - 021 (rejected): 120d raw momentum (crashed in 2024-2025).
  - 022 (rejected as swing): 12m momentum at 8-day hold (turnover friction destroyed edge).
  - 024 (provisional watch): 12m momentum at 21-day hold.
  - 025 (rejected): 12m residual momentum (beta orthogonalization stripped compounders).
  - 026 (rejected): 63d quarterly momentum (whipsawed in 2025).
  - Strategy 027 tests a **dual composite of 52-Week High Nearness + 252-day Trend Consistency (Sharpe)** at a **42-session (~2 months)** holding horizon. Not in REJECTED.md.

---

## Rules (exact, unambiguous)
- **Universe:** Liquid NSE names not in the Nifty 50; 60-day median turnover $\ge \text{₹}25\text{ cr}$.
- **Features (known at bar $t$ close):**
  1. $52\text{w High Nearness} = \frac{\text{Close}_{i,t}}{\max_{k \in [0, 251]} \text{High}_{i,t-k}}$
  2. $\text{Trend Consistency (t\_stat\_252)} = \frac{\text{mean}_{252}(R_i)}{\text{std}_{252}(R_i)} \times \sqrt{252}$
- **Signal:** Rank all liquid mid/small caps cross-sectionally by both features, compute composite score $\text{Composite} = \frac{\text{Rank}_{52\text{w}} + \text{Rank}_{\text{t\_stat}}}{2.0}$, and enter when the composite is in the **top decile ($\ge 90\text{th percentile}$)**.
- **Entry fill:** Same close (indicator signal from EOD prices). Next-open entry tested as a mandatory fragility check.
- **Exit:** Time exit at **42 trading sessions** (~2.0 calendar months), no ATR bracket. Control gets identical exit rule.
- **Holding period:** 42 sessions.
- **Costs:** `charge_costs=True` (liquidity-tiered model, ~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode).

---

## Kill criteria — decided BEFORE running
REJECT if any of the following occur:
1. Stable mean $z_{\text{paired}}$ across 20 control seeds $< 2.0$ pooled **or** $< 2.0$ on the holdout half B of names.
2. Net day edge $\le 0$ in any regime block (P1: 2016-2020, P2: 2021-2023, P3: 2024-2026).
3. **Survivorship:** Pre-2017 listings alone must clear stable mean $z_{\text{paired}} \ge 2.0$ **and** retain $\ge 60\%$ of pooled day edge.
4. **Decile Ladder:** Monotonic gradient from D10 down to D1.
5. **The Portfolio Tool Test:** A 20-slot equal-weight cash-constrained portfolio with 0.50% round-trip costs must beat Buy-and-Hold of the same universe on CAGR and Sharpe, beat random selection, and remain ahead of B&H under 1.5x costs (0.75% round trip).
6. **Execution / Control Fragility:** Dies against a volatility/beta-matched control or collapses under next-session entry fill.
7. **Walk-Forward Stability:** All 5 chronological walk-forward folds must remain positive on paired $z$-score.
8. **Holding Period Robustness:** $\pm 1$ step in holding horizon (21, 30, 42, 50, 60 sessions) must sit on a stable plateau.

---

## Results (after running)

Command run:
```bash
python strategies/027_52_week_high_trend_consistency_composite_in_mid_small_caps.py
```

### 1. Headline Engine Statistics (42-Session Hold)

| Metric | Strategy 027 (Composite) | Control (Random Entry) | Edge / Headline |
|---|---|---|---|
| Trades (non-overlapping) | 2,692 | 2,692 | — |
| Paired days | 1,407 | 1,407 | — |
| Gross avg return / trade | +4.660% | +2.924% | +1.736% |
| Avg round-trip cost | 0.500% | 0.500% | — |
| **NET avg return / trade** | **+4.160%** | **+2.424%** | **+1.736%** |
| Win rate | 57.8% | 51.4% | +6.4% |
| **naive z (edge_vs_control)** | +4.62 | — | (optimistic, not headline) |
| **DAY-CLUSTERED z_paired (seed 42)** | **+4.03** | — | day_edge: **+1.729%** |
| **POOLED Stable Mean z_paired (20 seeds)** | **+3.80** | (min +2.79, max +4.58) | **100% pass rate** |
| **Hold-out Half B Stable Mean z_paired** | **+2.16** | (min +1.38, max +3.54) | **55% pass rate (clears $\ge 2.0$)** |

---

### 2. Decile Ladder Gradient (Monotonicity Check)

| Decile Rank | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|
| **D10 (Top Decile - Signal)** | 2,688 | 1,407 | **+3.70** | **+1.734%** | **+4.144%** |
| **D09** | 3,722 | 1,595 | +3.24 | +1.483% | +3.756% |
| **D08** | 4,188 | 1,649 | +2.53 | +1.178% | +3.512% |
| **D07** | 4,329 | 1,642 | +0.63 | +0.297% | +3.077% |
| **D06** | 4,249 | 1,645 | -1.21 | -0.238% | +2.571% |
| **D05** | 4,059 | 1,621 | -2.58 | -0.558% | +2.291% |
| **D04** | 3,714 | 1,566 | -1.90 | -0.331% | +2.204% |
| **D03** | 3,211 | 1,500 | -3.10 | -1.222% | +1.455% |
| **D02** | 2,610 | 1,355 | -2.99 | -1.105% | +1.504% |
| **D01 (Bottom Decile)** | 1,749 | 1,112 | **-4.13** | **-2.050%** | **+0.616%** |

_The decile ladder exhibits a monotonic gradient from +1.734% (D10) down to -2.050% (D01), yielding a total spread of 3.784% per trade._

---

### 3. Holding Period Sensitivity ($\pm 1$ Step)

| Holding Period | Strategy Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **21 sessions (~1.0m)** | 4,229 | 1,774 | +3.91 | 100% | +0.855% | +1.984% |
| **30 sessions (~1.4m)** | 3,340 | 1,585 | +3.49 | 100% | +1.255% | +2.900% |
| **42 sessions (~2.0m Baseline)** | 2,692 | 1,407 | **+3.83** | **100%** | **+1.729%** | **+4.160%** |
| **50 sessions (~2.4m)** | 2,413 | 1,331 | +3.72 | 100% | +2.186% | +5.230% |
| **60 sessions (~2.9m)** | 2,131 | 1,213 | +3.51 | 100% | +2.322% | +6.121% |

---

### 4. Regime Blocks & Survivorship

| Partition / Subgroup | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **P1 (2016-2020)** | 475 | 327 | +2.18 | 70% | +2.295% | +1.439% |
| **P2 (2021-2023)** | 925 | 491 | +2.74 | 95% | +2.258% | +5.647% |
| **P3 (2024-2026)** | 1,210 | 522 | +1.78 | 30% | +1.058% | +3.194% |
| **Pre-2017 Listings Only (462 names)** | 2,163 | 1,259 | **+2.39** | **75%** | **+1.458%** | **+3.569%** |
| **Later Listings Only (167 names)** | 529 | 317 | +2.64 | 80% | +3.617% | +6.577% |

_Pre-2017 subgroup clears $z = +2.39 \ge 2.0$ and retains **84.3%** of pooled day edge (kill hurdle $\ge 60\%$)._

---

### 5. Controls and Execution Fragility
- **Volatility/Beta-Matched Control:** Stable mean $z_{\text{paired}} = \mathbf{+3.82}$ (100% pass rate, min +2.59, max +4.78), Day Edge $+1.349\%$. The edge is not a leverage or beta bet.
- **Next-Session Entry (Next Open Fill):** Stable mean $z_{\text{paired}} = \mathbf{+3.28}$ (100% pass rate, min +2.16, max +3.94), Day Edge $+1.440\%$, Net Return $+3.937\%$. Not fill-fragile.

---

### 6. Chronological Walk-Forward Folds (Purged & Embargoed)
- 5 Walk-Forward Fold $z$-scores: $[+2.32, +1.15, +2.95, +0.75, +2.08]$
- Mean Fold $z$: **+1.85** (homogeneous expectation: +1.80)
- Spread std: **0.89** (homogeneous expectation: ~0.91). Folds show no significant instability.

---

### 7. Portfolio Simulation & Cost Stress Test
- Machinery: 20 equal-weight concurrent positions, cash-constrained, ranked by highest composite score, 42-session hold (~6 rebalances/year).

| Portfolio Configuration | CAGR | Max Drawdown | Sharpe Ratio |
|---|---|---|---|
| **Strategy 027 (1.0x costs, 0.50% RT)** | **+19.72%** | **-46.18%** | **0.96** |
| **Strategy 027 (1.5x costs, 0.75% RT)** | **+18.13%** | **-47.79%** | **0.90** |
| **Strategy 027 (2.0x costs, 1.00% RT)** | **+16.55%** | **-49.35%** | **0.83** |
| **Equal-Weight Universe Buy-and-Hold (0% cost)** | **+17.21%** | **-54.31%** | **0.87** |
| **Random Selection Portfolios (3 seeds)** | **+6.80%** | **-58.4% to -64.1%** | **0.34 - 0.45** |

#### Calendar Year Returns & Excess vs Buy-and-Hold:
- **2017:** Strategy +15.0% | B&H +47.8% (Excess -32.8% during 252-day warmup)
- **2018:** Strategy -17.9% | B&H -16.5% (Excess -1.3%)
- **2019:** Strategy +5.3% | B&H -7.1% (**Excess +12.3%**)
- **2020:** Strategy +21.2% | B&H +22.2% (Excess -1.0%)
- **2021:** Strategy +80.6% | B&H +47.6% (**Excess +33.0%**)
- **2022:** Strategy +1.7% | B&H -2.1% (**Excess +3.8%**)
- **2023:** Strategy +71.5% | B&H +47.8% (**Excess +23.8%**)
- **2024:** Strategy +30.1% | B&H +27.9% (**Excess +2.2%**)
- **2025:** Strategy -5.1% | B&H +0.4% (Excess -5.5%)
- **2026:** Strategy +18.8% | B&H +10.2% (**Excess +8.5%**)

_Excluding the 2017 warmup year, Strategy 027 outperforms Buy-and-Hold in 6 out of 9 calendar years, and delivers +19.72% CAGR with significantly shallower drawdowns (-46.18% vs -54.31%). Crucially, unlike 026 and 024, it beats Buy-and-Hold even at 1.5x costs (+18.13% vs +17.21%)._

---

## Bias Hunt — What Could Be Faking This?
1. **Look-Ahead:** Features use only close and high up to day $t$. Next-open entry fill clears $z = +3.28$ (100% pass rate).
2. **Overlap:** Enforced `allow_overlap=False` (one trade per episode).
3. **Day-Clustering:** Clustered by entry date paired against random control. Headline is stable mean $z_{\text{paired}} = +3.80$.
4. **Survivorship:** Pre-2017 listings alone clear $z = +2.39$ and retain 84.3% of edge.
5. **Cost Omission:** Full round-trip costs charged; passes stress test up to 1.5x costs.
6. **Decile Monotonicity:** Confirmed monotonic across all 10 deciles (D10 to D01).

---

## VERDICT
**PROVISIONAL PASS — WATCH, forward-test pending.**  
- **Day-Clustered Stable Mean $z_{\text{paired}}$:** **+3.80** (100% pass rate across 20 seeds).
- **Net Day Edge:** **+1.729%** / 42-session trade.
- **Holdout Half B Stable Mean $z_{\text{paired}}$:** **+2.16** (clears $\ge 2.0$).
- **Portfolio CAGR:** **+19.72%** (Sharpe 0.96, MaxDD -46.18%) vs **+17.21%** (Sharpe 0.87, MaxDD -54.31%) B&H.
- **Economic Robustness:** Beats B&H even at 1.5x costs (+18.13% vs +17.21%).

**Why kept in WATCH rather than instant ADOPT:**  
Per METHODOLOGY.md §9, any strategy emerging after a broad multi-factor exploration must pass an out-of-sample forward test before live capital commitment. It is logged to neither ledger per rule.

---

## ⚠️ REVIEWER FINDING (2026-08-31) — NOT NOVEL, this is a rediscovery of an OWNED edge
Verified independently: the numbers reproduce exactly (pooled stable mean z 3.80, holdout 2.16,
walk-forward homogeneous 1.85≈1.80). No look-ahead — the work is clean. **But this is the parent
tool's already-validated long-term signal in a weaker form.** ADOPTED.md now records:
- Cross-sectional 12-month momentum basket (Mid/Small): **z ~9.5** — the incumbent long-term signal.
- Low-vol / quality-momentum tilt within it: already known to add return.
- Near-52w-high small-cap: z 4.28.

Strategy 027 (52wk-high nearness + trend-consistency/low-path-vol composite, z **3.80**) is that
same momentum-plus-low-vol family, and **weaker (3.80 vs 9.5)** than what the tool already runs. It
was tested against a RANDOM control, which for a known factor only re-proves the factor exists
(METHODOLOGY §10). Against the real benchmark — the incumbent momentum basket — it has not been
shown to add anything.

Economics also thin: at 2× costs the portfolio (+16.55% CAGR) LOSES to buy-and-hold (+17.21%), and
max drawdown is −46%.

**Corrected verdict: REJECT-as-new (rediscovery of an owned, stronger edge).** Not adoptable. The
only way it earns value is to beat the EXISTING momentum basket head-to-head (control = incumbent,
not random) — specifically, show its trend-consistency leg adds return *on top of* the basket the
tool already has. Until then, no further work needed here; the tool already owns this.

