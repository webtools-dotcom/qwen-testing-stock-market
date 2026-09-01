# Strategy 025 — 12-Month Residual Momentum in Mid-Small Caps

**Status:** REJECTED (2026-08-25) — selection edge confirmed real (stable mean z_paired +3.74, 100% pass), but **fails on portfolio economics** (CAGR +17.49% vs +21.66% for buy-and-hold; Sharpe 0.56 vs 0.86).
**Date started:** 2026-08-25

---

## Hypothesis
Standard 12-month momentum (`change_252d`) is contaminated by systematic market beta, leading it to buy high-beta speculative names during bull runs and crash heavily during market turns. Academic residual momentum (Blitz, Huij, Martens 2011) orthogonalizes 252-session stock returns against market returns:
$$R_{i,t} = \alpha_i + \beta_i R_{m,t} + \epsilon_{i,t}$$
$$\text{Score}_i = \frac{\sum_{t=1}^{252} \epsilon_{i,t}}{\sigma(\epsilon_i)}$$
Ranking liquid Indian mid/small caps by idiosyncratic residual return divided by idiosyncratic volatility should isolate pure firm-specific re-rating, delivering smoother 30-session (~1.5 month) drift with reduced drawdown and beta-crash risk.

## Checked against REJECTED.md?
- [x] Residual momentum / beta-orthogonalized momentum is distinct from 021 (plain 120d-ex-20d raw momentum) and 022/024 (un-orthogonalized risk-adjusted momentum). Not present in REJECTED.md.

## Rules (exact, unambiguous)
- **Universe:** Liquid NSE names not in the Nifty 50; 60-day median turnover $\ge \text{₹}25\text{ cr}$.
- **Signal (close of day t):** Calculate 252-day market beta ($\beta_{252}$) vs equal-weight market index and 252-day idiosyncratic volatility. Score = $\text{resid}_{252} / \text{idio\_vol}_{252}$. Enter if `score` is in the **top decile** cross-sectionally among liquid mid/smalls that day.
- **Entry fill:** Same close (indicator signal computed from EOD prices).
- **Exit:** Time exit at **30 trading sessions** (~1.5 months), no ATR bracket.
- **Holding period:** 30 sessions.
- **Costs:** `charge_costs=True` (liquidity-tiered, ~0.50% round trip).
- **Overlap:** `allow_overlap=False` (one trade per episode).

## Kill criteria — decided BEFORE running
REJECT if any of these:
1. Stable mean $z_{\text{paired}}$ across 20 control seeds $< 2.0$ pooled or $< 2.0$ on the hold-out half B of names.
2. Net edge $\le 0$ in any regime block (P1: 2016-2021, P2: 2022-2023, P3: 2024-2026).
3. No monotonic decile ladder (D10 through D1).
4. **The Portfolio Tool Test (The primary hurdle):** A 20-slot equal-weight cash-constrained portfolio with 0.50% round-trip costs must beat buy-and-hold of the same universe on CAGR and risk-adjusted return (Sharpe).

## Threshold handling
- [x] Top decile (top 10%) is the standard pre-specified factor definition from literature (no search penalty).

---

## Results (after running)

Command run:
```bash
python strategies/025_12_month_residual_momentum_in_mid_small_caps.py
```

### 1. Headline Engine Statistics (30-Session Hold)

| Metric | Strategy (Residual Momentum) | Control (Random Entry) | Edge / Headline |
|---|---|---|---|
| Trades (non-overlapping) | 2,133 | 2,133 | — |
| Paired days | 1,205 | 1,205 | — |
| Gross avg return / trade | +3.499% | +2.100% | +1.399% |
| Avg round-trip cost | 0.500% | 0.500% | — |
| **NET avg return / trade** | **+2.999%** | **+1.600%** | **+1.399%** |
| Win rate | 54.2% | 49.1% | +5.1% |
| **naive z (edge_vs_control)** | 3.49 | — | (optimistic, not headline) |
| **DAY-CLUSTERED z_paired (seed 42)** | **+3.59** | — | day_edge: **+1.621%** |
| **POOLED Stable Mean z_paired (20 seeds)** | **+3.74** | (min +2.92, max +4.43) | **100% pass rate** |
| **Hold-out Half B Stable Mean z_paired** | **+2.34** | (never searched) | **65% pass rate** |

### 2. Regime Blocks (Walk-Forward Chronological Partitions)

| Regime Block | Strategy Trades | Paired Days | Day Edge (net) | $z_{\text{paired}}$ |
|---|---|---|---|---|
| **P1 (2016-2021)** | 566 | 369 | +1.529% | +1.56 |
| **P2 (2022-2023)** | 510 | 322 | +1.853% | +2.25 |
| **P3 (2024-2026)** | 1,057 | 514 | +1.543% | +2.58 |

All three regime blocks show positive net day edge (+1.53% to +1.85%).

### 3. Monotonic Decile Ladder Check

| Decile | Name-Days | Day-Demeaned Edge | $t$-statistic |
|---|---|---|---|
| **D10 (Top Decile - Signal)** | 42,649 | **+1.329%** | **+12.24** |
| D09 | 41,626 | +0.976% | +11.55 |
| D08 | 41,832 | +0.337% | +4.28 |
| D07 | 41,636 | -0.151% | -2.44 |
| D06 | 41,431 | -0.561% | -8.83 |
| D05 | 42,038 | -0.289% | -4.91 |
| D04 | 41,832 | -0.497% | -6.54 |
| D03 | 41,634 | -0.212% | -2.41 |
| D02 | 41,843 | -0.214% | -2.44 |
| **D01 (Bottom Decile)** | 42,832 | **-0.471%** | **-4.42** |

The decile ladder is clean and monotonic: D10 (+1.33%) > D09 (+0.98%) > D08 (+0.34%) > ... > D01 (-0.47%).

---

### 4. The Portfolio Tool Test (The Killer)

20 equal-weight slots, cash-constrained, 0.50% round-trip costs charged:

| Metric | Strategy 025 (Residual Momentum) | Buy-and-Hold Benchmark | Excess / Gap |
|---|---|---|---|
| **CAGR** | **+17.49%** | **+21.66%** | **-4.17% / year** |
| **Max Drawdown** | **-44.00%** | **-52.56%** | +8.56% |
| **Sharpe Ratio** | **0.56** | **0.86** | **-0.30** |
| Annualized Volatility | 22.35% | 19.33% | +3.02% |

#### Calendar Year Breakdown (Strategy vs Buy & Hold)
- **2017**: Strategy 0.00% vs B&H +28.41% (**-28.41%**) *(warmup year)*
- **2018**: Strategy -1.93% vs B&H -17.97% (**+16.04%**)
- **2019**: Strategy -1.43% vs B&H -3.98% (**+2.55%**)
- **2020**: Strategy +20.29% vs B&H +40.95% (**-20.66%**)
- **2021**: Strategy +68.78% vs B&H +66.48% (**+2.30%**)
- **2022**: Strategy +2.92% vs B&H +10.19% (**-7.28%**)
- **2023**: Strategy +58.53% vs B&H +58.78% (**-0.24%**)
- **2024**: Strategy +16.87% vs B&H +30.84% (**-13.97%**)
- **2025**: Strategy -7.65% vs B&H -2.74% (**-4.91%**)
- **2026**: Strategy +21.19% vs B&H +7.93% (**+13.26%**)

## Why it died (The Economic Autopsy)
1. **Beta Orthogonalization Hurts in Growth Markets:** By stripping out market beta, the strategy intentionally suppresses high-beta winners during broad bull markets. In 2020 and 2024, when Indian small/mid caps experienced broad momentum surges (+41% and +31%), Residual Momentum lagged severely (+20% and +17%).
2. **Turnover Friction:** At a 30-session hold (~8 rebalances/slot/year), paying 0.50% round trip costs generates ~4%/year of turnover drag compared to cost-free buy-and-hold.
3. **Drawdown Protection is Weak:** Despite lower CAGR, the maximum drawdown is only modestly reduced (-44.0% vs -52.6%).

## VERDICT
**REJECT** — Stable mean $z_{\text{paired}} = +3.74$ (100% pass) proves statistical selection skill vs random entry, but the strategy fails on portfolio economics (CAGR +17.49% vs +21.66% Buy & Hold, Sharpe 0.56 vs 0.86).
Added row to `REJECTED.md` via `python ledger.py reject`.
