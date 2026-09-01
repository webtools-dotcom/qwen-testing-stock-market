# Strategy 001 — RSI(14) < 30 mean reversion (WORKED EXAMPLE)

This is the reference example. It shows the full honest loop and, usefully, ends in a REJECT on
the universe tested — so it also demonstrates the failure→REJECTED.md flow. Real numbers below
were produced by `python strategies/001_rsi_mean_reversion.py`, not estimated.

---

## Hypothesis
Liquid stocks that get oversold (RSI<30) over-sell short-term and bounce over the next ~6 days,
so buying the dip beats random entry. (A classic, well-documented mean-reversion effect.)

## Checked against REJECTED.md?
- [x] RSI<30 itself isn't rejected — but note the sister project found it works ONLY in Mid/Small
  caps and **excludes Large**. This example tests a LARGE-cap universe on purpose, to show what a
  no-edge result looks like.

## Rules
- **Universe:** 34 large-cap NSE names (Nifty-large proxy), liquid ≥ ₹25cr/day. Survivorship:
  present-day constituents only — a known bias, flagged (see below).
- **Entry signal:** RSI(14) < 30 at the bar's close.
- **Entry fill:** close of the signal bar (example simplification; a stricter test enters next
  open — for a 6-day hold it barely moves the result).
- **Exit:** ATR stop (2×) / ATR target (2×) / 6-day time exit, whichever first. Honest gap fills.
- **Holding period:** 6 bars.
- **Costs:** charged (~0.50%/round-trip at this liquidity).

## Kill criteria (pre-committed)
- Reject if z_paired < 2.0 OR net edge ≤ 0. (RSI<30 is Wilder's pre-set number, so no search
  penalty applies.)

---

## Results (measured)

```
python strategies/001_rsi_mean_reversion.py
```

| Metric | Value |
|---|---|
| Usable stocks | 33 (TATAMOTORS.NS ticker failed to download) |
| Trades (non-overlapping) | 422 |
| Paired days | 225 |
| Gross avg/trade | +0.380% |
| Avg round-trip cost | 0.500% |
| **NET avg/trade** | **−0.120%** |
| Control (random) net/trade | −0.301% |
| Edge vs control | +0.181% |
| naive z (edge_vs_control) | 0.86 (p=0.39) — optimistic, not the headline |
| **DAY-CLUSTERED z_paired** | **−0.30** |
| Win rate | 50.9% |

## Bias hunt — what could be faking this?
- **No edge to fake here** — the result is negative, so the interesting question is the opposite:
  is the +0.181% raw "edge vs control" real? No: naive z is only 0.86 (insignificant), and once
  day-clustered the paired edge goes NEGATIVE (z_paired −0.30). The small raw edge was the market,
  not stock selection.
- **Costs matter:** gross was +0.38%, net −0.12%. A zero-cost backtest would have shown a "small
  positive edge" and lied. This is exactly why costs are always charged.
- **Survivorship:** present-day large-caps only — mildly *flatters* the result if anything, and it
  still failed, which strengthens the rejection.
- **Cap tier:** matches the sister project's prior — RSI<30 has no demonstrable edge in large-caps.
  The edge lives in Mid/Small. Testing it here was to show a clean no-edge example.

## VERDICT
**REJECT on the large-cap universe** — z_paired −0.30, net −0.12%/trade. Not distinguishable from
(actually slightly worse than) random entry once the market factor is paired out. To pursue RSI<30
for real, re-run on a **Mid/Small-cap** universe, where the sister project demonstrated a positive
day-clustered edge.

> Teaching point: naive z 0.86 → paired z −0.30, and gross +0.38% → net −0.12%. Two different
> corrections (day-clustering and costs) each turned a "maybe" into a "no". Headline the corrected
> numbers, never the raw ones.

If this were a fresh idea, log it now:
```bash
python ledger.py reject "RSI<30 mean reversion on large-caps" "z_paired -0.30, net -0.12%/trade — no edge, market-only; RSI<30 edge is Mid/Small not Large"
```
_(Not logged here because RSI<30-in-Mid/Small is a survivor, not a rejection — only the large-cap
variant fails. Kept as an example instead.)_
