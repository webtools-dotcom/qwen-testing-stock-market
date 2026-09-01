# Strategy 018 — Overnight vs Intraday Tug of War Divergence

## Hypothesis
A daily bar is two different markets glued together. The **overnight** leg (prev close → open)
prices in news, global cues and institutional/block interest with essentially no intraday
liquidity provision; the **intraday** leg (open → close) is dominated by high-churn retail and
prop order flow, which supplies liquidity and applies transient price pressure. Lou, Polk &
Skouras (2019, JFE, "A tug of war") show these two components of the *same* past return carry
**opposite-signed** persistence in US equities: the overnight component continues, the intraday
component reverses. India should show this at least as strongly — retail is an unusually large
share of NSE cash turnover and is overwhelmingly intraday.

So: a stock that has been **accumulated overnight while being sold intraday** (positive 20-day
overnight sum, negative 20-day intraday sum) has informed demand hidden under transient retail
supply. Over the next 6-10 sessions the transient supply exhausts and the price catches up to the
overnight signal.

**Why this is not a rediscovery:** every idea in REJECTED.md is built from close-to-close
constructs (RSI, RoC, 50-day highs, candlestick bodies, relative strength, breakouts, gap
reversals). None of them decompose the bar into its two flows. The signal is deliberately
*orthogonal in sign* to close-to-close momentum: it fires on names whose net 20-day return can be
anything, and it is the **split** that carries the information, not the total.

## Checked against REJECTED.md?
- [x] Not present, not a trivial variant. Nearest neighbours are "Gap-down intraday reversal in
  uptrend" (single-day gap, rejected) and "Relative Strength Rotation" (close-to-close). This is a
  20-day flow decomposition, a different construct. Explicitly tested below against a
  **momentum-matched control** so it cannot pass by smuggling in plain 20-day reversal.

## Rules (exact, unambiguous)
- **Universe:** 94-name liquid NSE panel (cache `nifty_research_150_5y`, 5y daily), turnover_60d
  ≥ ₹25cr/day. Survivorship: constituents as of today — stated as a caveat, not corrected.
- **Features**, all known at the close of day *t*:
  - `on_20  = Σ_{k=t-19..t} ln(open_k / close_{k-1})`   (overnight component)
  - `id_20  = Σ_{k=t-19..t} ln(close_k / open_k)`       (intraday component)
  - `tug    = on_20 − id_20`
- **Entry signal:** on day *t*, among liquid names, `tug` in the **top decile cross-sectionally
  that day** AND `on_20 > 0` AND `id_20 < 0`.
  Decile is the pre-committed convention from the source literature — not a scanned cutoff. The
  two sign conditions are signs, not thresholds. **No tuned number in the entry rule.**
- **Entry fill:** same close (all inputs are close-of-day indicators). A **next-open** variant is
  run as a fragility check.
- **Exit:** engine defaults — stop 2×ATR(14), target 2×ATR(14), else time exit.
- **Holding period:** 8 bars (mid of the requested 6-10 day swing window).
- **Costs:** `charge_costs=True`, liquidity-tiered.

## Kill criteria — decided NOW, before any number
Reject if ANY of these:
1. Stable **mean** z_paired < 2.0 across 20 control seeds (single-draw z is not accepted).
2. Net edge vs control ≤ 0 after costs.
3. Most-recent walk-forward fold has negative z_paired.
4. The **decile gradient is not monotone-ish** — if D10 is a lone spike with D9/D8 flat or
   negative, it is a fitted extreme, not a mechanism.
5. **The edge disappears against the momentum-matched control** (entries drawn from bars with a
   similar 20-day close-to-close return). If it does, this is plain reversal wearing a costume.
6. It dies at next-open fill (execution-fragile).
7. Per §8: if it clears pooled but the mid/small subgroup (the tradeable half) fails on its own,
   it is a pooling artifact, not an adoption.

## Threshold handling
- [x] Pre-committed from theory (top decile + sign conditions; horizon 8 = mid of the requested
      6-10 band). A decile sensitivity grid is reported as a **robustness** check, and its result
      is NOT used to reselect the headline.
- **Search context (§9):** this is idea #1 of this session — a single pre-registered test, no
  prior candidates scanned. Stated in the verdict.

---

## Results (after running)

Command run:
```
python strategies/018_overnight_vs_intraday_tug_of_war_divergence.py
```
Panel: 88 liquid NSE names, 5y daily, turnover_60d >= Rs 25cr, costs charged, non-overlapping.

| Metric | Value |
|---|---|
| Trades (non-overlapping) | 2,140 |
| Paired days | 1,010 |
| Gross avg/trade | +0.304% |
| Avg round-trip cost | 0.500% |
| **NET avg/trade** | **-0.196%** |
| Control (random) net | -0.166% |
| **Net edge vs control /trade** | **-0.030%** (negative) |
| naive z (edge_vs_control) | -0.23 (p=0.82) — optimistic, not the headline |
| DAY-CLUSTERED z_paired (single draw, seed 42) | -0.00 |
| **MEAN z_paired across 20 control seeds** | **+0.58** (min -0.09, max +1.54) |
| Pass rate (seeds with z_paired >= 2.0) | **0%** |
| Per-fold z_paired | F1 -0.30, F2 +1.81, F3 +0.11, **F4 (most recent) +0.98** |
| Next-open z_paired | stable mean +0.71, 0% pass |
| vs momentum-matched control | stable mean +0.20, 0% pass |
| Holding-period band 6-10d | 6d -0.01, 7d -0.15, 8d +0.59, 9d -0.37, 10d +0.35 — all 0% pass |
| Robust to +/-1 decile step? | No gradient exists to be robust to (see below) |

### Subgroup (METHODOLOGY sec 8)
| Subgroup | n | Net/trade | Edge | Stable mean z_paired | Pass |
|---|---|---|---|---|---|
| Mid/Small (the tradeable half) | 1,513 | -0.042% | +0.353% | +0.84 | 5% |
| Large (Nifty 50) | 627 | -0.568% | -0.432% | -1.04 | 0% |

Neither half clears. The mid/small half is the only one with a positive gross-of-control edge and
it still lands at 0.84 with a 5% pass rate — noise.

### Decile gradient — the decisive kill
The hypothesis predicts a monotonic rise in forward edge from D1 (sold overnight, bought intraday)
to D10 (bought overnight, sold intraday). Measured:

| Decile | n | Net/trade | Edge vs control | z_paired |
|---|---|---|---|---|
| D1 | 2,146 | -0.199% | -0.033% | -0.04 |
| D2 | 3,200 | -0.167% | -0.000% | -0.05 |
| D3 | 3,750 | -0.231% | -0.064% | -0.17 |
| D4 | 4,018 | -0.181% | -0.014% | -0.49 |
| D5 | 4,275 | -0.229% | -0.062% | -0.87 |
| D6 | 4,235 | -0.267% | -0.101% | -0.99 |
| D7 | 3,978 | -0.275% | -0.109% | -1.34 |
| D8 | 3,695 | -0.225% | -0.058% | -0.88 |
| D9 | 3,135 | -0.202% | -0.036% | -0.93 |
| D10 | 2,250 | -0.115% | +0.051% | +0.11 |

There is **no gradient at all** — the spread from D1 to D10 is +0.08%/trade against a 0.50% cost
stack, and the middle deciles are the *worst*, which no version of the hypothesis predicts. The
overnight/intraday split carries essentially zero cross-sectional information about 6-10 day
forward returns in this universe. This is the cleanest possible refutation: the mechanism itself
is absent, so no threshold, horizon or subgroup could rescue it.

## Bias hunt — what could be faking this?
Nothing needed to be explained away; the result is negative. For completeness, the checks that
would have mattered if it had looked good were all run anyway:
- **Look-ahead:** `on_20`/`id_20` use only bars up to and including *t*; the cross-sectional rank
  uses only same-day values of other stocks. Entry at the same close (indicator convention).
  Next-open fill also run: +0.71, still nothing.
- **Overlap:** `allow_overlap=False` throughout (engine default).
- **Day-clustering:** headline is the stable mean z_paired over 20 control seeds, never the naive z.
  Here the naive z (-0.23) and the paired z (-0.00) agree, so clustering was not hiding anything.
- **Cost omission:** `charge_costs=True`. Gross was +0.304%/trade — genuinely positive, and
  genuinely smaller than the 0.500% round-trip. A cost wall, not an edge.
- **Threshold fit:** none to deflate — the entry rule has no scanned number. The decile grid and
  6-10d horizon band were run as robustness, not selection, and both are flat/negative.
- **Momentum contamination:** the momentum-matched control (same date, same 20d close-to-close
  return quintile, ordinary tug rank) leaves stable mean z_paired +0.20. Whatever tiny wobble the
  random control showed was not stock selection.
- **Survivorship:** universe is today's constituents; uncorrected. Irrelevant to a rejection —
  survivorship would bias *toward* a false positive, and there isn't one.

## VERDICT
**REJECT.** Stable mean z_paired **+0.58** across 20 control seeds (0% of seeds clear 2.0), net
edge **-0.030%/trade** after costs, no decile gradient (D1->D10 spread +0.08% vs a 0.50% cost
stack), mid/small subgroup +0.84 and large-cap -1.04, nothing in the 6-10 day band, and only
+0.20 against a momentum-matched control. The overnight/intraday decomposition — which is a real,
published US anomaly — does not transfer to 6-10 day swing horizons on liquid NSE names.

**Search context (sec 9):** this was idea #1 of the session, a single pre-registered test with no
prior candidates scanned. That makes the negative result stronger, not weaker: there is no
multiple-testing story that could have suppressed a real edge here.

If REJECT -> added a row to `REJECTED.md`? [x]
