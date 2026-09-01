# Strategy 031 — NR7 Volume Dryup Pullback in Uptrend

**Status:** **REJECTED** (2026-08-31) — While clearing against a random control (mean $z = +2.49$), the signal **fails against an uptrend-matched control** (stable mean $z = \mathbf{+1.02}$, 0% pass rate, day edge $+0.017\%$) proving it is generic uptrend beta rather than an entry edge, **loses decisively to the incumbent momentum basket** ($z = \mathbf{-0.94}$, day edge $-0.197\%$), fails pre-2017 survivorship ($z = +1.60$), and stalls in walk-forward folds (mean fold $z = +0.78$, Fold 2 negative at $-0.01$). Logged to REJECTED.md.  
**Date tested:** 2026-08-31  

---

## Hypothesis
In classical price-action literature (Toby Crabel 1990), a Narrowest Range in 7 sessions (NR7) accompanied by volume dryup ($< 0.60\times$ 20-day average) in an established uptrend ($\text{Close} > \text{SMA}_{50}$ and $\text{Close} > \text{SMA}_{200}$) reflects selling exhaustion and liquidity contraction prior to an explosive trend continuation impulse. Holding for 15 sessions (~3 calendar weeks) aims to harvest the subsequent expansion.

---

## Checked against REJECTED.md and ADOPTED.md?
- [x] **Checked against REJECTED.md:**
  - 007 (rejected): ID/NR4 volatility breakout ($z = 1.45$).
  - 006 (rejected): 3-day volatility contraction pullback to 50 SMA ($z = -0.88$ recent fold).
  - 028 (rejected): Volume-dryup pullback in trend consistency leaders ($z = 1.54$ holdout B).
  - Strategy 031 specifically isolates Toby Crabel's NR7 pattern with volume dryup in uptrends across 10 years of NSE data.

---

## Rules (exact, unambiguous)
- **Universe:** Liquid NSE names not in the Nifty 50; 60-day median turnover $\ge \text{₹}25\text{ cr}$.
- **Entry signal (bar $t$ close):**
  1. $\text{Range}_t = \frac{\text{High}_t - \text{Low}_t}{\text{Close}_t}$ is the minimum range of the last 7 sessions ($\text{NR7}$).
  2. $\text{Volume}_t < 0.60 \times \text{SMA}_{20}(\text{Volume})$.
  3. $\text{Close}_t > \text{SMA}_{50,t}$ and $\text{Close}_t > \text{SMA}_{200,t}$ (structural uptrend).
- **Entry fill:** Same close.
- **Exit:** Time exit at **15 trading sessions** (~3 calendar weeks), no ATR bracket.
- **Costs:** `charge_costs=True` (liquidity-tiered model, ~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode).

---

## Kill criteria — decided BEFORE running
REJECT if any of the following occur:
1. Fails to clear stable mean $z_{\text{paired}} \ge 2.0$ against an **uptrend-matched control** (stocks in uptrend at random bars).
2. Fails against the **incumbent momentum basket** (§10) — if it adds negative alpha over what the tool already owns.
3. Stable mean $z_{\text{paired}} < 2.0$ on the pre-2017 survivorship subgroup.
4. Dies in walk-forward folds (mean fold $z < 1.0$ or negative folds).

---

## Results (after running)

Command run:
```bash
python strategies/031_nr7_volume_dryup_pullback_in_uptrend.py
```

### 1. Headline Engine Statistics (15-Session Hold)

| Control Type | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate ($\ge 2.0$) | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **vs RANDOM Control** | 9,132 | 1,731 | **+2.49** | 80% | +0.300% | +0.813% (ctrl +0.609%) |
| **vs UPTREND Control** | 9,132 | 1,617 | **+1.02** | **0%** | **+0.017%** | +0.813% (ctrl +0.842%) |
| **vs INCUMBENT MOM Basket (§10)** | 9,132 | 1,622 | **-0.94** | **0%** | **-0.197%** | +0.813% (ctrl +0.962%) |
| **Holdout Half B (vs Random)** | 4,598 | 1,399 | +2.37 | 70% | +0.518% | +1.029% (ctrl +0.634%) |

---

### 2. Holding Period Sensitivity

| Holding Horizon | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **6 sessions** | 13,221 | 1,861 | +2.33 | 80% | +0.225% | +0.118% (ctrl -0.069%) |
| **8 sessions** | 12,031 | 1,841 | +2.38 | 80% | +0.322% | +0.213% (ctrl +0.040%) |
| **10 sessions** | 10,931 | 1,798 | +3.10 | 100% | +0.495% | +0.441% (ctrl +0.191%) |
| **15 sessions (Baseline)** | 9,132 | 1,731 | +2.41 | 80% | +0.300% | +0.813% (ctrl +0.609%) |
| **21 sessions** | 7,787 | 1,658 | +2.06 | 50% | +0.303% | +1.232% (ctrl +1.014%) |

---

### 3. Regime Blocks & Survivorship

| Partition / Subgroup | Trades | Paired Days | Stable Mean $z_{\text{paired}}$ | Pass Rate | Net Day Edge | Net Return / Trade |
|---|---|---|---|---|---|---|
| **P1 (2016-2020)** | 1,413 | 529 | +1.51 | 15% | +0.692% | +0.290% (ctrl +0.071%) |
| **P2 (2021-2023)** | 3,164 | 616 | +1.32 | 5% | +0.146% | +1.342% (ctrl +1.211%) |
| **P3 (2024-2026)** | 4,383 | 552 | +1.17 | 0% | +0.369% | +0.427% (ctrl +0.381%) |
| **Pre-2017 Listings Only (462 names)** | 7,301 | 1,674 | **+1.60** | **30%** | **+0.212%** | **+0.697%** (ctrl +0.535%) |
| **Later Listings Only (167 names)** | 1,831 | 718 | +1.35 | 0% | +0.381% | +1.274% (ctrl +0.895%) |

---

### 4. Walk-Forward Chronological Folds
- 5 Walk-Forward Fold $z$-scores: $[+1.94, -0.01, +0.33, +1.34, +0.31]$
- Mean Fold $z$: **+0.78** (severely underpowered). Fold 2 is negative.

---

## Bias Hunt — What Faked the Apparent Random-Control Pass?
1. **Uptrend Beta Disguise:** The apparent edge against random entries ($z = +2.49$) is entirely an artifact of requiring $\text{Close} > \text{SMA}_{50}$ and $\text{Close} > \text{SMA}_{200}$. When tested against an **uptrend-matched control** (stocks in uptrend selected at random bars), the edge collapses to **$+0.017\%$** with $z = \mathbf{+1.02}$ (0% pass rate).
2. **Incumbent Factor Duplication:** When benchmarked against the incumbent momentum basket (§10), NR7 volume dryup produces negative excess ($z = \mathbf{-0.94}$, day edge $-0.197\%$).
3. **Survivorship Failure:** Pre-2017 listings alone achieve only $z = +1.60$ (0/3 regime blocks clear $z \ge 2.0$).

---

## VERDICT
**REJECT.**
- **Day-Clustered Stable Mean $z_{\text{paired}}$ vs Uptrend Control:** **+1.02** (0% pass rate).
- **vs Incumbent Momentum Basket (§10):** **-0.94** (Net Day Edge: **-0.197%**).
- **Survivorship Subgroup:** **+1.60** (fails $\ge 2.0$).
- Logged to `REJECTED.md`.

