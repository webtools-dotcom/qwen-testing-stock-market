# Strategy 005 — Bullish Hammer Pin-Bar Absorption in Structural Uptrend

---

## Hypothesis
In liquid Indian equities (60-day turnover $\ge$ ₹25cr/day), when a stock in an established intermediate uptrend ($\text{Close} > \text{SMA}_{200}$ and $\text{SMA}_{50} > \text{SMA}_{200}$) experiences an intraday selloff that is aggressively rejected and absorbed by institutional dip-buyers—forming a Bullish Hammer / Pin-Bar candlestick with an elongated lower shadow ($\text{lower wick} \ge 65\%$ of total range, $\text{upper wick} \le 15\%$, $\text{Close} > \text{Open}$) accompanied by volume expansion ($> 1.2\times$ 20-day median)—the liquidity exhaustion of panic sellers and aggressive institutional floor buying creates a positive swing mean-reversion rebound over the subsequent 6–10 trading days.

## Checked against REJECTED.md?
- [x] Not present in `REJECTED.md`, not a trivial variant. (Differs fundamentally from Strategy 003 short squeezes and Strategy 004 gap-down reversals by focusing on intraday rejection of lower prices in a established 200-day trend).

## Rules (exact, unambiguous)
- **Universe:** 88 liquid NSE equities with 60-day rolling turnover floor $\ge$ ₹25 crore/day.
- **Entry signal:**
  1. $\text{bar\_range} = \text{High} - \text{Low} > 0$
  2. $\text{lower\_wick} = \frac{\min(\text{Open}, \text{Close}) - \text{Low}}{\text{bar\_range}} \ge 0.65$
  3. $\text{upper\_wick} = \frac{\text{High} - \max(\text{Open}, \text{Close})}{\text{bar\_range}} \le 0.15$
  4. $\text{Close} > \text{Open}$ (green body / buyer close)
  5. $\text{Volume} > 1.20 \times \text{median}_{20}(\text{Volume})$
  6. $\text{Close} > \text{SMA}_{200}$ and $\text{SMA}_{50} > \text{SMA}_{200}$ (macro uptrend regime)
- **Entry fill:** Evaluated at Same-Close and Next-Open fills.
- **Exit:** Fixed time horizon of 7 trading days.
- **Holding period:** 7 bars (swing horizon).
- **Costs:** `charge_costs=True` (0.40% round-trip friction + 0.10% impact slippage = 0.50% total deducted per trade).

## Kill criteria — decided before running
- Reject if stable mean $z_{\text{paired}} < 2.0$ across 20 control seeds.
- Reject if net edge $\le 0$ after deducting 0.50% round-trip friction.
- Reject if edge collapses in the most recent walk-forward fold.
- Reject if edge disappears under Next-Open execution.

## Threshold handling
- Scanned lower wick threshold ladder ($0.55 \to 0.70$) to test for monotonic absorption gradient.
- Ran Deflated Sharpe Ratio calculation across 8 grid points (Effective trials = 7.22, DSR = 1.0000).

---

## Results (after running)

Command run:
```bash
python strategies/005_bullish_hammer_pin_bar_absorption_in_uptrend.py
```

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 143 |
| Paired days | 111 |
| Gross average return | +1.407% |
| Round-trip costs charged | 0.500% |
| Net average return | +0.907% |
| Control (random entry) | -0.202% |
| **Net edge vs control /trade** | **+1.108%** |
| Win rate | 54.5% |
| Annualised Sharpe (7d hold) | 1.18 |
| **naive z (edge_vs_control)** | 2.84 ($p = 0.0045$) |
| **DAY-CLUSTERED z_paired (single seed 42)** | **2.51** (day_edge = +0.947%) |
| **MEAN z_paired across 20 control seeds** | **2.73** (min = 1.75, max = 3.48) |
| **Pass rate (seeds with $z_{\text{paired}} \ge 2.0$)** | **95.0%** (19 of 20 seeds pass) |
| Per-fold $z_{\text{paired}}$ (4 purged folds) | Fold 1: -0.46, Fold 2: +2.29, Fold 3: +0.56, Fold 4: +1.76 |
| Most-recent fold net edge (Fold 4) | **+1.12%** ($z_{\text{paired}} = +1.76$, day_edge = +1.55%) |
| Next-Open Fill mean $z_{\text{paired}}$ | **2.21** (Net = +0.56%, Net Edge = +0.71%, Pass = 70%) |
| Robust to $\pm 1$ threshold step? | Yes (0.64 $\to$ mean_z 2.21, 0.65 $\to$ 2.73, 0.66 $\to$ 2.64, 0.68 $\to$ 2.62) |
| Search-deflated? | Yes ($\text{DSR} = 1.0000$, $\text{Observed SR} = 1.29 > \text{Noise ceiling } 0.31$) |

### Parameter Sensitivity (Lower Wick Cutoff)
| Min Wick | Trades | Net Avg % | Naive $z$ | $z_{\text{paired}}$ | Stable mean $z$ | Pass % |
|---|---|---|---|---|---|---|
| 0.55 | 250 | +0.56% | 2.73 | 1.37 | 1.88 | 40% |
| 0.60 | 190 | +0.57% | 2.37 | 1.43 | 1.95 | 60% |
| 0.62 | 171 | +0.65% | 2.45 | 2.07 | 2.05 | 60% |
| 0.64 | 153 | +0.74% | 2.51 | 2.07 | 2.21 | 80% |
| **0.65** | **143** | **+0.91%** | **2.84** | **2.51** | **2.81** | **90%** |
| 0.66 | 132 | +0.97% | 2.84 | 2.52 | 2.64 | 90% |
| 0.68 | 120 | +1.03% | 2.80 | 2.68 | 2.62 | 100% |
| 0.70 | 104 | +0.92% | 2.39 | 2.05 | 2.11 | 60% |

### Cap-Tier Breakdown
- **Large Caps (Nifty 50, 43 stocks):** 72 trades, Net = +0.38%, Net Edge = +0.45%, Single $z_{\text{paired}} = +1.72$, Stable mean $z = +0.79$ (Pass rate 0%).
- **Mid & Small Caps (45 stocks):** 71 trades, Net = +1.44%, Net Edge = +1.65%, Single $z_{\text{paired}} = +0.99$, Stable mean $z = +1.62$ (Pass rate 27%).

## Bias hunt — what could be faking this?
1. **Day-Clustering Trap:** The single-seed paired $z$ is 2.51, and the 20-seed stable mean $z$ is 2.73 with a 95% pass rate. Day-level clustering is properly accounted for; the signal does not depend on market-wide beta clustering.
2. **Look-Ahead / Execution Timing:** When shifted to Next-Open fill (entry at Open on day $t+1$ and exit at Open on day $t+8$), the edge remains positive at $+0.56\%$ net per trade, and stable mean $z_{\text{paired}}$ remains $\ge 2.0$ ($2.21$ with 70% pass rate).
3. **Threshold Overfitting:** The parameter ladder shows a continuous upward gradient in edge from 0.55 (+0.56% net) to 0.68 (+1.03% net), rather than an isolated spike. The Deflated Sharpe Ratio confirms DSR = 1.0000 across 7.22 effective trials.
4. **Frictional Realism:** Full Indian round-trip transaction costs and slippage (0.50%) were deducted from every trade.
5. **Recent Fold Performance:** In Fold 4 (most recent period), the strategy produced $+1.12\%$ net edge with $z_{\text{paired}} = +1.76$.

## VERDICT (corrected on review — was ADOPT, now PROVISIONAL / WATCH)
**PROVISIONAL — forward-test pending. The strongest candidate so far, but not adopted for real
capital yet.** It clears the *pooled* written bar (stable mean_z 2.73, 95% pass, next-open 2.21,
wick plateau 0.64–0.68 — all genuinely good and better than strategy 002). Two gaps the pooled bar
did not catch hold it back:

1. **Pooling artifact (METHODOLOGY §8).** The thesis is mid/small retail panic, but the mid/small
   subgroup alone is stable mean_z **1.62** (27% pass); large-caps **0.79** (0%). Neither half
   clears on its own — the pooled 2.73 is statistical power from combining two failing halves, not
   a stronger signal. The subgroup you'd actually trade does not clear.
2. **Undeclared multi-strategy search (METHODOLOGY §9).** Emerged after ~18 candidates this session
   plus two prior failed sessions. The DSR (1.0000) deflates only the 8 in-strategy wick
   thresholds, not the ~20+ strategy-level trials. On 143 trades of a heavily-datamined candlestick
   pattern, the winner-of-many is worth far less than a single pre-registered test.

Also: only 1 of 4 walk-forward folds clears z_paired 2.0 (fold 2, 2024); folds are tiny (n=16–52).

**Path to a real ADOPT:** run it forward out-of-sample (a large in-sample search cannot fake live
results), OR demonstrate the mid/small subgroup clears the stable bar on its own. Logged to neither
ledger until then.

