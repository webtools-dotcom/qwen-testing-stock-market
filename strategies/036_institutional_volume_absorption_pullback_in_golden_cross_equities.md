# Strategy 036 — Institutional Volume Absorption Pullback in Golden Cross Equities

**Status:** **REJECTED** (2026-09-01)  
**Headline Result:** Pooled stable mean $z_{\text{paired}} = +2.20$ vs random control appears eligible on the surface, but fatally fails the adversary battery:
- **Loses head-to-head to AR-001 (Golden Cross RSI<30) baseline** (METHODOLOGY §10): $z_{\text{paired}} = \mathbf{-1.11}$, Net Day Edge $= \mathbf{-0.406\%}$ across 267 paired days.
- **Fails tradeable subgroups** (METHODOLOGY §8): Half A stable mean $z = \mathbf{+0.73}$ (0% pass rate), Half B stable mean $z = \mathbf{+1.78}$ (35% pass rate) — the pooled 2.20 is an artifact of combining two failing halves.
- **Dies in the most recent fold** (METHODOLOGY §7): Fold 5 (2024–2026) turns negative with $z_{\text{paired}} = \mathbf{-0.07}$.
- **Fails pre-2017 survivorship alone** (METHODOLOGY §4): stable mean $z = \mathbf{+1.91}$ (pass rate 55%).  
**Date tested:** 2026-09-01  

---

## Hypothesis
In liquid Indian equities (NSE mid/small caps with 60-day turnover $\ge \text{₹}25\text{ cr}$), when a stock in a strong secular bull market—established by a classical Golden Cross ($\text{SMA}_{50} > \text{SMA}_{200}$ and $\text{Close} > \text{SMA}_{200}$) with trailing 1-year momentum $\ge 30\%$—experiences a short-term pullback into oversold territory ($\text{RSI}_{14} \le 35$), an accompanying institutional volume surge ($\text{Volume} \ge 1.2\times \text{Volume}_{20d,\text{median}}$) represents climactic turnover absorption by institutional dip-buyers. This accumulation supposedly halts the decline and creates an asymmetric rebound over an 8-trading-day swing horizon.

---

## Checked against REJECTED.md and ADOPTED.md?
- [x] **Checked against REJECTED.md:**
  - 028: Volume-dryup pullback in trend consistency leaders died (low volume hurt). This strategy tests the exact opposite: volume *surge* / absorption on dips.
  - 031: NR7 volume dryup pullback died.
  - 035: Adopted AR-001 is the incumbent baseline for oversold Golden Cross stocks.
- [x] **Checked against ADOPTED.md & METHODOLOGY §10:**
  - Strategy 035 (AR-001) is the owned baseline in this family.
  - Per METHODOLOGY §10, Strategy 036 must be tested head-to-head against AR-001.

---

## Rules (exact, unambiguous — FROZEN)
- **Universe:** Liquid NSE Mid and Small Cap equities (excluding Nifty 50 index constituents); 60-day median turnover $\ge \text{₹}25\text{ crore/day}$.
- **Features (known at bar $t$ close):**
  1. $\text{SMA}_{50, t} = \frac{1}{50}\sum_{k=0}^{49} \text{Close}_{t-k}$
  2. $\text{SMA}_{200, t} = \frac{1}{200}\sum_{k=0}^{199} \text{Close}_{t-k}$
  3. $\text{Change}_{252d, t} = (\text{Close}_t / \text{Close}_{t-252} - 1) \times 100 \ge 30.0\%$
  4. $\text{RSI}_{14, t} = \text{Wilder's RSI}(14) \le 35.0$
  5. $\text{Volume Ratio}_{t} = \text{Volume}_t / \text{median}(\text{Volume}_{t-19..t}) \ge 1.20$
  6. $\text{Turnover}_{60d, t} \ge \text{₹}25\text{ cr}$
- **Signal:** Enter when ALL conditions are met at bar $t$ close:
  $\text{Close}_t > \text{SMA}_{200, t}$ AND $\text{SMA}_{50, t} > \text{SMA}_{200, t}$ AND $\text{Change}_{252d} \ge 30\%$ AND $\text{RSI}_{14} \le 35.0$ AND $\text{Vol Ratio} \ge 1.20$.
- **Entry fill:** Same close (standard daily-bar indicator convention). Next-open entry fill tested as execution check.
- **Exit:** Fixed time exit at **8 trading sessions**.
- **Costs:** `charge_costs=True` (~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode per stock).

---

## Kill criteria — decided BEFORE running
REJECT if any of the following occur:
1. Stable mean $z_{\text{paired}} < 2.0$ pooled across 20 control seeds vs Random Control.
2. Failure vs Incumbent AR-001 (§10): $z_{\text{paired}} < 2.0$ or Net Day Edge $\le 0$.
3. Subgroup failure (§8): Either Half A or Half B fails to clear stable mean $z_{\text{paired}} \ge 2.0$.
4. Survivorship failure (§4): Pre-2017 listings fail to clear stable mean $z_{\text{paired}} \ge 2.0$.
5. Recent fold failure (§7): Most recent walk-forward fold (Fold 5) is negative.
6. Execution collapse (§4): Next-open stable mean $z < 2.0$.

---

## Results (measured)

Command run:
```bash
python strategies/036_institutional_volume_absorption_pullback_in_golden_cross_equities.py
```

### 1. Headline Statistics (8-Session Hold)

| Metric | Value |
|---|---|
| Usable stocks | 561 Mid/Small liquid NSE stocks |
| Strategy Trades (non-overlapping) | 1,160 |
| Next-Open Trades | 1,079 |
| Gross Return / Trade | +1.615% |
| Round-Trip Cost Charged | 0.500% |
| **NET Return / Trade** | **+1.115%** |
| Win Rate | 56.8% |
| **vs RANDOM Control Stable Mean $z_{\text{paired}}$ (20 seeds)** | **+2.20** (min +1.60, max +3.03) |
| Random Control Pass Rate ($\ge 2.0$) | **70.0%** (14 of 20 seeds pass) |
| Net Day Edge vs Random Control | **+0.567%** / paired day |
| **vs INCUMBENT AR-001 $z_{\text{paired}}$ (§10)** | **-1.11** |
| Net Day Edge vs Incumbent AR-001 | **-0.406%** / paired day |
| Paired Days vs Incumbent | 267 |

---

### 2. Subgroup Robustness (§8) & Survivorship (§4)

| Slice | Trades | Stable Mean $z_{\text{paired}}$ | Pass Rate | Status |
|---|---|---|---|---|
| **Half A** (arbitrary 50% split) | 652 | **+0.73** | 0% | **FAIL** (violates §8) |
| **Half B** (arbitrary 50% split) | 508 | **+1.78** | 35% | **FAIL** (violates §8) |
| **Pre-2017 listings** (survivorship) | 913 | **+1.91** | 55% | **FAIL** (violates §4) |
| **Post-2017 listings** | 247 | **+0.53** | 0% | FAIL |

*Neither Half A nor Half B clears the bar alone. The pooled +2.20 is purely a pooling artifact.*

---

### 3. Chronological Walk-Forward Folds (§7)

| Fold | Period | Trades | $z_{\text{paired}}$ |
|---|---|---|---|
| Fold 1 | 2017-09 to 2019-07 | 92 | +0.57 |
| Fold 2 | 2019-07 to 2021-04 | 72 | +1.08 |
| Fold 3 | 2021-04 to 2023-01 | 307 | +1.72 |
| Fold 4 | 2023-01 to 2024-10 | 471 | +3.12 |
| **Fold 5 (Most Recent)** | **2024-10 to 2026-08** | **217** | **-0.07** (**FAIL**) |

*The edge flips negative in the most recent market regime (Fold 5 $z = -0.07$), failing METHODOLOGY §7.*

---

### 4. Execution Check & Threshold Sensitivity (§6)

- **Next-Open Entry Fill:** Net return remains positive (+1.469%), but stable mean $z_{\text{paired}} = \mathbf{+1.51}$ (only 20% pass rate).
- **RSI Cutoff Sensitivity:**
  - $\text{RSI} \le 30.0$: Net $+1.887\%$, Mean $z = +2.47$ (402 trades)
  - $\text{RSI} \le 32.0$: Net $+1.641\%$, Mean $z = +1.97$ (627 trades)
  - $\text{RSI} \le 35.0$: Net $+1.115\%$, Mean $z = +2.20$ (1,160 trades)
  - $\text{RSI} \le 38.0$: Net $+0.741\%$, Mean $z = +1.03$ (1,897 trades)

---

## Bias Hunt & Failure Analysis
1. **Head-to-head defeat vs incumbent (METHODOLOGY §10):** Adding the $\text{Volume} \ge 1.2\times$ filter to pullbacks loosens the RSI threshold from 30 to 35, bringing in marginal trades that underperform AR-001 by $-0.406\%$ per day ($z = -1.11$).
2. **Pooling artifact (METHODOLOGY §8):** The pooled $z = 2.20$ is driven entirely by combining two halves that fail independently ($z = 0.73$ in Half A and $z = 1.78$ in Half B).
3. **Regime decay (METHODOLOGY §7):** The strategy stops working in the 2024–2026 cycle ($z = -0.07$).

---

## VERDICT
**REJECT** — Fails vs incumbent AR-001 ($z = -1.11$, day edge $-0.406\%$, §10), fails Half A subgroup ($z = +0.73$, §8), fails Half B subgroup ($z = +1.78$, §8), and dies in recent fold (Fold 5 $z = -0.07$, §7). Logged to `REJECTED.md`.
