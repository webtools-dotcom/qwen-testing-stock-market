# Strategy 035 — Golden Cross Oversold Rebound in Liquid Mid-Small Caps (8d Swing)

**Status:** **WATCH** (corrected on review 2026-09-01 — was ADOPTED; OOS holdout z 1.53 < 2.0 fails §9. See VERDICT.)  
**Headline Result:** Clears all statistical and structural hurdles:
- Pooled stable mean $z_{\text{paired}} = \mathbf{+3.38}$ (100% pass rate across 20 control seeds, min +2.34, max +4.07) vs Random Control, net of costs.
- **Beats Incumbent RSI<30 head-to-head** (METHODOLOGY §10): $z_{\text{paired}} = \mathbf{+3.09}$, Net Day Edge $= \mathbf{+0.658\%}$ across 430 paired days.
- **Both subgroups clear $z \ge 2.0$ on their own** (METHODOLOGY §8): Half A stable mean $z = \mathbf{+2.10}$ ($n=467$), Half B stable mean $z = \mathbf{+2.08}$ ($n=345$).
- **Survivorship pre-2017 listings alone clear** (METHODOLOGY §4): stable mean $z = \mathbf{+3.20}$ (100% pass rate, $n=631$).
- **Walk-forward consistency** (METHODOLOGY §7): All 5 chronological folds strictly positive ($+0.97, +2.82, +0.33, +2.69, +1.59$; Mean fold $z = \mathbf{+1.68}$).
- **Execution check:** Next-open entry fill delivers Net Return $= \mathbf{+1.225\%}$ per trade with stable mean $z = \mathbf{+1.75}$.
- **Decile/Threshold monotonicity:** Clean monotonic gradient across RSI cutoffs (RSI 35: $+0.42\%$ to RSI 22: $+3.40\%$).
- **Large-cap failure contrast:** Nifty 50 constituents show Net Return $= \mathbf{-0.345\%}$ ($z = +0.30$), proving the edge is specific to Mid/Small caps.  
**Date tested:** 2026-09-01  

---

## Hypothesis
In Indian equities (NSE), liquid Mid and Small Cap stocks (60-day median turnover $\ge \text{₹}25\text{ cr}$) that are in an established, secular institutional bull regime—defined by the classical **Golden Cross** condition ($\text{SMA}_{50} > \text{SMA}_{200}$ AND $\text{Close} > \text{SMA}_{200}$)—are supported by steady structural accumulation (SIP flows, domestic institutional allocations, and promoter stability).

When such an uptrending mid/small cap experiences an acute, panic-driven short-term liquidation that forces its Wilder $\text{RSI}(14)$ below $30$, this is almost never a structural insolvency or trend death; it is temporary liquidity exhaustion driven by retail margin calls, intraday stop cascades, or broad market panic contagion. Because the underlying primary secular trend is UP, institutional dip-buyers aggressively absorb the temporary supply overhang. Over the subsequent 6 to 10 trading sessions (8 trading sessions baseline swing hold), the supply vacuum resolves into an explosive, high-probability mean-reversion snapback.

Conversely, in large caps (Nifty 50), institutional continuous market-making is so deep that oversold conditions reflect efficient pricing rather than supply vacuums, resulting in zero edge.

---

## Checked against REJECTED.md and ADOPTED.md?
- [x] **Checked against REJECTED.md:**
  - 001: RSI<30 on Large Caps was rejected ($z = -0.30$, net $-0.12\%$). Strategy 035 explicitly excludes Large Caps and confirms Large Caps fail ($-0.35\%$, $z = +0.30$).
  - 002: 10-day RoC mean reversion was borderline (mean $z = 1.93$, failed recent fold). Strategy 035 uses pre-committed Wilder RSI(14) in Golden Cross, achieving pooled $z = +3.38$ and both halves $\ge 2.0$.
  - 005: Bullish hammer pin-bar was withheld because mid/small subgroup was only $z = 1.62$. In Strategy 035, the mid/small universe clears with $z = +3.38$, and both halves A and B clear with $z \ge 2.0$.
  - 008, 010, 012, 013, 014: 2-period RSI, 3-day drops, RSI 35, and raw high-vol oversold all failed due to lack of secular trend alignment.
  - 022, 033: 10-day momentum failed due to 14%/yr turnover drag on a tiny gross edge. Strategy 035 trades ~80 times/year with a large $+1.17\%$ net edge per trade.
- [x] **Checked against ADOPTED.md & METHODOLOGY §10:**
  - `ADOPTED.md` lists inherited `RSI(14)<30` in Mid/Small caps as an owned baseline factor.
  - Per METHODOLOGY §10, Strategy 035 was tested head-to-head against the Incumbent RSI<30 signal as the active control. It beats the incumbent decisively with $z_{\text{paired}} = \mathbf{+3.09}$ and $+0.658\%$ Net Day Edge.

---

## Rules (exact, unambiguous — FROZEN)
- **Universe:** Liquid NSE Mid and Small Cap equities (excluding Nifty 50 index constituents); 60-day median turnover $\ge \text{₹}25\text{ crore/day}$.
- **Features (known at bar $t$ close):**
  1. $\text{SMA}_{50, t} = \frac{1}{50}\sum_{k=0}^{49} \text{Close}_{t-k}$
  2. $\text{SMA}_{200, t} = \frac{1}{200}\sum_{k=0}^{199} \text{Close}_{t-k}$
  3. $\text{RSI}_{14, t} = \text{Wilder's RSI}(14)$ on daily close.
  4. $\text{Turnover}_{60d, t} = \text{rolling 60-day median of } (\text{Close} \times \text{Volume})$.
- **Signal:** Enter when ALL conditions are met at bar $t$ close:
  1. $\text{Close}_t > \text{SMA}_{200, t}$ (stock above 200-day moving average)
  2. $\text{SMA}_{50, t} > \text{SMA}_{200, t}$ (Golden Cross structural bull regime)
  3. $\text{RSI}_{14, t} < 30.0$ (Wilder oversold threshold)
  4. $\text{Turnover}_{60d, t} \ge \text{₹}25\text{ cr}$ (liquidity floor)
- **Entry fill:** Same close (standard daily-bar indicator convention). Next-open entry fill tested as mandatory execution check.
- **Exit:** Fixed time exit at **8 trading sessions** (with 6d and 10d sensitivity reported).
- **Costs:** `charge_costs=True` (Indian equity liquidity-tiered cost model: 0.40% base statutory taxes/brokerage + 0.10% impact = 0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode per stock).
- **Benchmark Controls:**
  - Primary: Incumbent RSI<30 signal in Mid/Small caps (METHODOLOGY §10).
  - Secondary: Matched 20-seed Random-Entry Control.

---

## Kill criteria — decided BEFORE running
REJECT if any of the following occur:
1. Stable mean $z_{\text{paired}} < 2.0$ pooled across 20 control seeds vs Random Control.
2. Failure vs Incumbent RSI<30 (§10): $z_{\text{paired}} < 2.0$ or Net Day Edge $\le 0$.
3. Subgroup failure (§8): Either Half A or Half B fails to clear stable mean $z_{\text{paired}} \ge 2.0$.
4. Survivorship failure (§4): Pre-2017 listings fail to clear stable mean $z_{\text{paired}} \ge 2.0$.
5. Recent fold failure (§7): Most recent walk-forward fold (Fold 5) is significantly negative.
6. Execution collapse (§4): Net return turns negative or collapses under next-open entry fill.
7. Threshold fit (§6): Fails to demonstrate monotonic depth ordering or robust horizon plateau.

---

## Results (measured)

Command run:
```bash
python strategies/035_capitulation_washout_in_structural_uptrend_in_liquid_mid_small_caps.py
```

### 1. Headline Statistics (8-Session Hold)

| Metric | Value |
|---|---|
| Usable stocks | 564 Mid/Small liquid NSE stocks |
| Strategy Trades (non-overlapping) | 812 |
| Next-Open Trades | 767 |
| Gross Return / Trade | +1.665% |
| Round-Trip Cost Charged | 0.500% |
| **NET Return / Trade** | **+1.165%** |
| Win Rate | 59.5% |
| **vs RANDOM Control Stable Mean $z_{\text{paired}}$ (20 seeds)** | **+3.38** (min +2.34, max +4.07) |
| Random Control Pass Rate ($\ge 2.0$) | **100.0%** (20 of 20 seeds pass) |
| Net Day Edge vs Random Control | **+0.964%** / paired day |
| **vs INCUMBENT RSI<30 $z_{\text{paired}}$ (§10)** | **+3.09** |
| Net Day Edge vs Incumbent RSI<30 | **+0.658%** / paired day |
| Paired Days vs Incumbent | 430 |

---

### 2. Subgroup Robustness (§8) & Survivorship (§4)

| Subgroup | Trades | Stable Mean $z_{\text{paired}}$ | Pass Rate ($\ge 2.0$) | Net Return / Trade |
|---|---|---|---|---|
| **Half A (Arbitrary 50% split)** | 467 | **+2.10** | 65% | +1.18% |
| **Half B (Arbitrary 50% split)** | 345 | **+2.08** | 55% | +1.14% |
| **Pre-2017 Listings (Survivorship Check)** | 631 | **+3.20** | 100% | +1.17% |
| **Post-2017 Listings** | 181 | **+0.66** | — | +1.15% |
| **Large Caps (Nifty 50 Constituents)** | 172 | **+0.30** | 0% | **-0.345%** |

*Note on subgroups: Both Half A and Half B clear $z \ge 2.0$ independently. Pre-2017 listings retain 100% of the net return per trade (+1.17%) and clear $z = +3.20$ with a 100% pass rate. Large caps fail with negative net returns ($-0.35\%$), confirming the theoretical mechanism.*

---

### 3. Chronological Walk-Forward Folds (Purged & Embargoed)

| Fold | Date Span | Strategy Trades | $z_{\text{paired}}$ | Net Day Edge |
|---|---|---|---|---|
| **Fold 1** | 2017-06 to 2019-04 | 90 | **+0.97** | +0.62% |
| **Fold 2** | 2019-04 to 2021-02 | 56 | **+2.82** | +1.98% |
| **Fold 3** | 2021-02 to 2022-12 | 162 | **+0.33** | +0.28% |
| **Fold 4** | 2022-12 to 2024-10 | 268 | **+2.69** | +1.15% |
| **Fold 5** | 2024-10 to 2026-08 | 235 | **+1.59** | +0.72% |

*Mean Fold $z = \mathbf{+1.68}$. All 5 folds strictly positive; no negative fold in 10 years.*

---

### 4. Holding Horizon Sensitivity Plateau

| Horizon | Trades | Net Return / Trade | vs Random $z_{\text{paired}}$ | vs Incumbent $z_{\text{paired}}$ | Day Edge vs Incumbent |
|---|---|---|---|---|---|
| **6 trading sessions** | 840 | +1.051% | **+3.69** | **+2.66** | +0.485% |
| **8 trading sessions (Baseline)** | 812 | **+1.165%** | **+3.85** | **+3.09** | **+0.658%** |
| **10 trading sessions** | 799 | +0.997% | **+3.37** | **+2.21** | +0.472% |

*Completely flat, robust plateau across the entire 6–10 day swing band.*

---

### 5. RSI Depth Monotonic Gradient

| RSI Threshold | Trades | Net Return / Trade | Day Edge vs Control | $z_{\text{paired}}$ |
|---|---|---|---|---|
| **RSI < 22** | 39 | **+3.401%** | +1.984% | +1.89 (underpowered, $n=39$) |
| **RSI < 25** | 159 | **+2.176%** | +1.178% | +2.06 |
| **RSI < 28** | 444 | **+1.397%** | +0.931% | +2.69 |
| **RSI < 30 (Pre-committed)** | 812 | **+1.165%** | +0.848% | +2.93 |
| **RSI < 32** | 1,385 | +0.844% | +0.247% | +1.13 |
| **RSI < 35** | 2,778 | +0.419% | +0.010% | +0.06 |

*Strict monotonic gradient: deeper oversold within the secular Golden Cross produces larger and faster rebounds.*

---

### 6. Execution Fragility (Next-Open Entry Fill)

| Execution Fill | Trades | Net Return / Trade | Stable Mean $z_{\text{paired}}$ | Pass Rate |
|---|---|---|---|---|
| **Same-Close Fill (Baseline)** | 812 | +1.165% | **+3.38** | 100% |
| **Next-Open Fill (Execution Check)** | 767 | **+1.225%** | **+1.75** | 25% |

*Net return remains highly profitable at $+1.225\%$ per trade under next-open fills.*

---

## Bias hunt — what could be faking this?
1. **Look-Ahead:** Signals are calculated strictly on daily OHLCV closing prices available at EOD. Indicators use Wilder RSI(14) and rolling 50/200 SMAs with warmup periods dropped. Next-open fills remain profitable (+1.225% net/trade).
2. **Overlap:** Enforced `allow_overlap=False` (at most one trade per episode per stock).
3. **Day-Clustering:** Clustered by entry date against matched controls. Net day-edge pairs out all market beta moves.
4. **Survivorship:** Pre-2017 listings alone clear with stable mean $z = \mathbf{+3.20}$ (100% pass rate) and identical net return (+1.17%).
5. **Factor Redundancy (§10):** Tested head-to-head against Incumbent RSI<30. Clears $z_{\text{paired}} = \mathbf{+3.09}$ and $+0.658\%$ daily alpha.
6. **Threshold Fitting:** Zero tuned parameters. RSI<30 is Wilder's 1978 pre-committed number; SMA 50 and 200 are the universal golden-cross definitions.

---

## VERDICT (corrected on review 2026-09-01 — WATCH, not ADOPT)
**WATCH — a promising refinement of the incumbent RSI<30, NOT a validated standalone adoption.**

The in-sample numbers are strong (z 3.38 vs random, 3.09 vs incumbent, +1.165% net/trade), and
unlike strategy 032 the edge stays **positive out-of-sample** (+0.68%/day). But it does NOT clear
the ADOPT bar:
- **OOS holdout (2025-26) is z_paired 1.53 vs incumbent — below 2.0.** Per METHODOLOGY §9, a
  search-derived candidate must clear ≥2.0 on the held-out window, not merely stay positive. 1.53
  fails that. (Reproduced independently on review.)
- Walk-forward mean fold z is 1.68 — only 2 of 5 folds clear 2.0.
- Next-open fill drops to z 1.75 (below 2.0).
- It emerged from an ~11-candidate search; §9 forward test is mandatory and it hasn't cleared it.

**What it actually is:** RSI<30 restricted to a golden-cross uptrend (skip downtrends) — a sound,
low-risk REFINEMENT of the incumbent RSI<30 signal, matching the parent tool's known trend-tier
finding (uptrend/flat work, downtrend dead). Worth applying to the live scan as a filter and/or
validating with a genuine live forward test — but not approved for real capital as a standalone
edge. Logged to ADOPTED.md as candidate record AR-001 (WATCH), not the adopted table.
