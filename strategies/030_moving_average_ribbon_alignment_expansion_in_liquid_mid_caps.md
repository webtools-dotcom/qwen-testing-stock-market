# Strategy 030 — Moving Average Ribbon Alignment Expansion in Liquid Mid-Caps

---

## Hypothesis
When a liquid mid/small cap stock transitions into a full multi-timeframe moving average ribbon alignment ($\text{EMA}_{10} > \text{SMA}_{20} > \text{SMA}_{50} > \text{SMA}_{200}$), it signals coordinated institutional accumulation across short-, medium-, and long-term trend horizons, generating persistent positive drift over a 15–21 session holding horizon ($H=21$ sessions baseline).

---

## Checked against REJECTED.md?
- [x] **Checked against REJECTED.md:**
  - 012 (rejected): High turnover 50-day high breakout ($z = 1.16$).
  - 014 (rejected): RSI 35 pullback in uptrend ($z = -0.65$).
  - 022 (rejected): 12m momentum at 8d hold (turnover friction destroyed edge).
  - 025 (rejected): Residual momentum.
  - 028 (rejected): Volume dry-up pullback in Sharpe leaders.
  - 029 (rejected): Intraday absorption pullback in trend consistency leaders ($z = 1.22$).
  - Strategy 030 specifically tests the **state-transition onset of multi-timeframe Moving Average Ribbon Alignment ($\text{EMA}_{10} > \text{SMA}_{20} > \text{SMA}_{50} > \text{SMA}_{200}$)** across 15–21 session holding horizons.

---

## Rules (exact, unambiguous)
- **Universe:** Liquid NSE names not in the Nifty 50; 60-day median turnover $\ge \text{₹}25\text{ cr}$.
- **Features (known at bar $t$ close):**
  1. `ribbon_now = (ema_10 > sma_20) & (sma_20 > sma_50) & (sma_50 > sma_200)`
  2. `ribbon_prev = ribbon_now.shift(1)`
  3. `ribbon_entry = ribbon_now & (~ribbon_prev)`: First day the multi-timeframe alignment occurs.
- **Entry fill:** Same close (indicator signal from daily bar). Next-open entry tested as execution check.
- **Exit:** Pure time exit at 21 trading sessions (~1 calendar month; 15 sessions tested for horizon stability).
- **Holding period:** 21 sessions.
- **Costs:** `charge_costs=True` (liquidity-tiered Indian equity cost model, ~0.50% round trip).
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
python strategies/030_moving_average_ribbon_alignment_expansion_in_liquid_mid_caps.py
```

| Metric | Strategy 030 (H=21d) | Strategy 030 (H=15d) | Random Control |
|---|---|---|---|
| Trades (non-overlapping) | 13,977 | 14,801 | 13,977 |
| Paired days | 2,037 | 2,067 | 2,037 |
| Gross avg return / trade | +0.667% | +0.606% | +0.415% |
| Avg round-trip cost | 0.500% | 0.500% | 0.500% |
| **NET avg return / trade** | **+0.167%** | **+0.106%** | **-0.085%** |
| Win rate | 54.3% | 53.0% | 49.8% |
| Net edge vs control / trade | +0.252% | +0.263% | — |
| **DAY-CLUSTERED z_paired (seed 0)** | **+3.58** | **+3.57** | — |
| **STABLE MEAN z_paired (20 seeds)** | **+3.10** (Pass 100%, [+2.47, +3.95]) | **+3.11** (Pass 100%, [+2.62, +4.11]) | — |
| Day edge | +0.305% | +0.305% | — |
| **Holdout Half B stable mean z** | **+1.96 (Pass 50%)** — **KILLED** | **+1.82 (Pass 20%)** — **KILLED** | — |
| Pre-2017 listings alone (survivorship) | **+2.83 (Pass 100%)** | **+2.92 (Pass 90%)** | — |
| Next-Open Entry fill | **+2.23 (Pass 80%)** | **+2.20 (Pass 60%)** | — |
| Walk-Forward Fold 1 (2018–2019) | Net -0.707%, Day Edge +0.553%, Mean z = +1.10 | Net -0.700%, Day Edge +0.448%, Mean z = +1.11 | — |
| Walk-Forward Fold 2 (2019–2021) | Net +0.968%, Day Edge **-0.072%**, Mean z = **-0.10** — **KILLED** | Net +0.685%, Day Edge **-0.154%**, Mean z = **-0.17** — **KILLED** | — |
| Walk-Forward Fold 3 (2021–2023) | Net -0.833%, Day Edge +0.429%, Mean z = +2.05 | Net -0.701%, Day Edge +0.430%, Mean z = +1.97 | — |
| Walk-Forward Fold 4 (2023–2024) | Net +0.719%, Day Edge +0.146%, Mean z = +1.10 | Net +0.648%, Day Edge +0.230%, Mean z = +1.79 | — |
| Walk-Forward Fold 5 (2024–2026) | Net -0.518%, Day Edge +0.302%, Mean z = +1.55 | Net -0.504%, Day Edge +0.243%, Mean z = +1.39 | — |
| **Portfolio Tool Test (1.0x costs)** | **CAGR +4.63%, Sharpe 0.43, MaxDD -44.12%** | **CAGR +1.17%, Sharpe 0.16, MaxDD -42.11%** | B&H: **+22.43%** |
| **Portfolio Tool Test (1.5x costs)** | **CAGR -1.03%, Sharpe -0.02, MaxDD -50.11%** | **CAGR -4.94%, Sharpe -0.34, MaxDD -52.51%** | **KILLED** |
| **Portfolio Tool Test (2.0x costs)** | **CAGR -6.41%, Sharpe -0.46, MaxDD -58.33%** | **CAGR -10.70%, Sharpe -0.82, MaxDD -72.79%** | **KILLED** |

---

## Bias hunt — what killed this strategy?
1. **Subgroup Collapse (§8)**: On the holdout Half B of names alone, stable mean $z_{\text{paired}}$ is only $+1.96$ at $H=21$ (50% pass rate) and $+1.82$ at $H=15$ (20% pass rate), failing the mandatory $\ge 2.0$ bar.
2. **Walk-Forward Inversion (§7)**: In Fold 2 (2019–2021), the strategy's day edge turns negative ($-0.072\%$ at $H=21$, $-0.154\%$ at $H=15$) with negative paired $z$-scores ($z = -0.10$ and $-0.17$).
3. **Razor-Thin Edge vs Turnover Friction**: While the signal generates statistical separation vs random entry ($z \approx 3.10$), the gross return per trade is only $+0.667\%$. After subtracting mandatory $0.50\%$ round-trip costs, the net return per trade is only $+0.167\%$. 
4. **Economic Collapse in Portfolio Simulation**: High trade count (13,977 trades across 10 years $\approx 70$ trades/slot/year) creates a massive $\sim 35\%/\text{year}$ friction drag. As a result, portfolio CAGR is only $+4.63\%$ at 1.0x costs (losing badly to Buy-and-Hold $+22.43\%$), and plunges to $-1.03\%$ at 1.5x costs and $-6.41\%$ at 2.0x costs.

---

## VERDICT
**REJECT** — Fails holdout Half B ($z = +1.96$, 50% pass rate), fails Walk-Forward Fold 2 (Day Edge $-0.072\%$, $z = -0.10$), and fails the Portfolio Tool Test (+4.63% CAGR vs +22.43% B&H, collapsing to -1.03% at 1.5x costs due to 35%/yr turnover friction drag on a thin +0.167% net return/trade).

Added a row to `REJECTED.md`? [x]

