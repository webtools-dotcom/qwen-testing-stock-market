# METHODOLOGY — how to backtest without fooling yourself

This is the non-negotiable procedure. Every number you report must come from a run that followed
it. If a step is skipped, say so explicitly and treat the result as unproven.

The whole document exists because of one fact, proven repeatedly in the sister project: **the
obvious way to backtest inflates edges, and the inflation is large enough to turn noise into a
confident "it works".** Each section below is a specific way that happens and how to stop it.

---

## The seven ways a backtest lies (check every one, every time)

### 1. No control → you measure the market, not the strategy
A strategy that returns +1.2%/trade in a bull market proves nothing if random entries also
returned +1.1%. **Always compare against a random-entry control on the same universe and same
period.** The edge is `strategy − control`, never the raw strategy return. Use
`edge_vs_control()` / `day_clustered_edge()`, which take a control trade list.

Build the control the same way you build the strategy: same stocks, same date range, same
holding period, entries placed at random (~10% of bars) instead of on the signal.

**A SINGLE control draw is one noisy sample — never headline it.** Its z_paired can land above or
below the bar by luck of the seed. This actually happened here: strategy 002 reported z_paired
2.40 on seed 42, but across 20 seeds the mean was 1.93 and only 50% of seeds cleared 2.0 — a
coin-flip dressed up as a pass. **Run `stable_day_clustered_z(strategy_trades, control_factory)`**
(≥20 seeds) and report `mean_z` and `pass_rate`. The ADOPT bar is on the **mean**, not a single
draw. `control_factory(seed)` just rebuilds the random control for that seed.

### 2. Overlapping trades → fake sample size
If your signal stays true for several days (RSI<30 can persist a week), entering on every true
bar creates ~3-4 near-identical trades sharing the same forward returns. Your n looks like 1,000
but carries ~300 independent observations, and the z-score is inflated by ~sqrt(inflation).
**Fix: `simulate_trades(..., allow_overlap=False)` (the default).** One trade per episode.

### 3. Day-clustering → fake sample size, across stocks
Even with non-overlapping trades per stock, hundreds of names can trigger on the *same day* and
share one market move. 1,125 trades over 112 days ≈ 112 observations, not 1,125. **This is THE
one that keeps killing "great" results.** In the sister project it took a z from 12.06 → 2.74.
**Fix: report `day_clustered_edge()`'s `z_paired` as the headline number.** It pairs each day's
strategy mean against the same day's control mean, netting out the market factor. The trade-level
z from `edge_vs_control()` is OPTIMISTIC — show it if you like, but never headline it.

**Bar to clear: z_paired ≥ 2.0, positive, net of costs.** Below that = not demonstrated = reject
(or "underpowered" only if paired-days < ~10, in which case gather more, don't approve).

### 4. Look-ahead → using tomorrow's information today
The classic killers:
- **Entry timing depends on the signal type — get this right:**
  - *Indicator signals* (RSI, moving averages, anything computed from the daily close): entering
    at that **same close** is the accepted EOD convention — you run the scan after the close and
    place a market-on-close or next-open order. `simulate_trades` enters at `close[i]` for this
    reason, and it matches the sister project. Fine for daily-bar indicator strategies.
  - *Event / news signals* (an earnings release, a filing, a corporate action): the event arrives
    intraday or overnight, so the same day's close is contaminated. Entry is the **NEXT session's
    open** — no exceptions. This is the look-ahead that flattered event-driven trading into a fake
    edge in the sister project (naive z 7.17 → paired 0.44). If your signal is event-based and you
    aren't entering next-open, your backtest is wrong.
- Exiting on an indicator at the same bar it's computed. RSI-recovery exits fill at the NEXT
  open — the engine already does this; don't undo it.
- Using `sma_200` / `change_252d` in the first 200/252 bars where they're NaN or backfilled.
  Drop the warmup, never forward-fill features.
- Survivorship: testing only stocks that exist *today* silently excludes everything that got
  delisted after failing. Prefer a point-in-time universe; if you can't, say so as a caveat.

### 5. Zero costs → an edge that evaporates on contact
Indian round-trip cost on a 4-6 day mid/small-cap hold is ~0.4-1.3% (STT, brokerage, GST, stamp,
slippage, liquidity impact) — the same order as the edge itself. **Always `charge_costs=True`.**
Report the NET figure. A gross edge that goes negative after costs is not a weak edge, it's no
edge. Illiquid small-caps look great gross and lose net — that's a cost wall, not a signal.

### 6. Threshold fitting → the best of many tries dressed up as one test
If you scanned RSI cutoffs 20,22,...,40 and reported the best, you ran 11 tests and picked the
max — that's ~88% likely to look "significant" on noise at 41 thresholds. Two defenses:
- **Pre-commit the threshold** from theory (RSI<30 is Wilder's number, not something you tuned).
  A pre-committed threshold carries no search penalty.
- If you must scan, run `block_bootstrap_pvalue()` (empirical family-wise correction) and
  `deflated_sharpe()` with `effective_trials()`. And check the result sits on a **plateau or a
  monotonic gradient**, not a lone spike — a real edge is robust to ±1 threshold step; a fitted
  one collapses.

### 7. One period → decay and regime hide in the average
A 5-year average can be carried entirely by one good year. **Walk it forward** with
`walk_forward_splits()` (purged + embargoed so labels can't straddle the boundary) and look at
each fold — especially the **most recent** one. An edge present in 2021-23 and gone in 2024-26 is
a dead edge with a flattering mean. Report per-fold, not just pooled.

---

### 8. Pooling artifact → significance from combining, not from signal
z_paired rises as you add paired days, because the standard error shrinks with more observations.
So a strategy can clear the pooled bar while the subgroup you'd actually trade does NOT. This
happened in strategy 005: pooled stable mean_z 2.73, but the mid/small subgroup (the one the
thesis is about) was only 1.62 and large-caps 0.79 — neither half clears alone; the pooled number
was power from combining two failing halves. **If your thesis names a subgroup (a cap tier, a
sector, a regime), that subgroup must clear the bar ON ITS OWN.** A pooled pass over a tradeable
subgroup that fails is not tradeable — you can't trade the pool if half of it (large-caps here)
carries no edge and just adds days.

### 9. The search across strategies → the multiple-testing you forget to count
The block-bootstrap and Deflated Sharpe correct for thresholds swept WITHIN one strategy. They do
NOT know about the OTHER strategies you tried. If you test 18 candidates in a session (plus more
in earlier sessions) and adopt the one that crossed z_paired 2.0, you selected the max of ~20+
noisy trials — and a pooled mean_z of 2.7 on the winner-of-20 is worth far less than the same
number from a single pre-registered test. **State the session's full candidate count in the
verdict**, and treat a borderline winner-of-many (mean_z just over 2, one good fold, tiny n) as
INCONCLUSIVE pending an OUT-OF-SAMPLE FORWARD TEST — the one check a large in-sample search cannot
fake. Deep, structural edges survive being the 1st idea tried; a pattern that only appears after
hammering 20 variants is usually the search finding noise.

### 10. Beating random ≠ new → for a KNOWN factor, the control is the existing signal
A random-entry control tests "is there any edge here at all?" That's the right question for a
genuinely new idea. It is the WRONG question when the idea sits in a factor family `ADOPTED.md`
already contains — momentum / 52-week-high / relative-strength / low-vol for the long-term book,
or RSI<30 mean-reversion for the swing book. Those factors already beat random by a mile (the
momentum basket is z ~9.5); a new strategy re-confirming that has discovered nothing.

**If your idea is in an owned family, the control must be the EXISTING signal, not random.** Rank
your candidate's trades against the incumbent basket on the same days, and ask: does it beat what
the tool ALREADY runs, or is it a weaker cousin of it? Strategy 027 (52wk-high + trend-consistency
composite, stable mean z 3.80) was a textbook example — real, careful, no look-ahead, but it is
the parent's own momentum-plus-low-vol signal in a WEAKER form (z 3.80 vs 9.5), tested against
random. Verdict: not novel, adds nothing over the incumbent. A rediscovery is a REJECT-as-new (note
it in the strategy file), not an adoption — unless it demonstrably beats the incumbent it duplicates.

## Naive-vs-paired: the discipline in one number

For anything that selects days or fires broadly, always report both and expect a big gap:

```
naive z (edge_vs_control)     : 7.17   <- do NOT trust or headline this
day-clustered z_paired        : 0.44   <- THE truth. REJECT.
```

If the naive z is high and the paired z is low, the naive number was high because the trades
piled onto a few good days (or because the control was also losing). That is not an edge.

---

## Verdict rules (decide the bar BEFORE you see the number)

- **ADOPT**: **mean** z_paired ≥ 2.0 across ≥20 control seeds (not a single lucky draw), positive
  net-of-cost edge, the most-recent fold non-negative (no significantly negative paired fold),
  robust to a ±1 threshold step, any search deflated, **the tradeable subgroup clears the bar on
  its own** (not just the pool — §8), and **if it emerged from a large multi-strategy search
  (§9), it has passed an out-of-sample forward test.** Survivorship caveats stated. If the edge
  only holds under same-close fills and dies at next-open, say so — it's execution-fragile.
  → A candidate that clears the *pooled* bar but fails the subgroup or has a heavy undeclared
    search behind it is a **provisional WATCH, forward-test pending** — not a live ADOPT. Log it
    to neither ledger until the forward test passes.
  → **"Passed the OOS/forward test" = the held-out window ITSELF clears z_paired ≥ 2.0 vs the
    correct control — NOT merely "still positive" or "still directionally right."** A holdout that
    is positive but z 1.5 has FAILED the bar and is a WATCH, however strong the in-sample number.
    In-sample significance never substitutes for the OOS bar. (Strategy 035: logged ADOPT on
    in-sample 3.09 while its own 2025-26 holdout was z 1.53 — that is a WATCH, corrected on review.)
- **REJECT**: z_paired < 2.0, OR net edge ≤ 0, OR it dies in the recent fold, OR it only survives
  by ignoring costs / using look-ahead / a fitted threshold. Write a one-line row into
  `REJECTED.md` so it's never re-tested.
- **INCONCLUSIVE (underpowered / borderline)**: positive lean but paired-days < ~10, or mean
  z_paired near the bar with a low pass_rate, or no walk-forward fold individually clears it, or
  the edge is execution-fragile. This is NOT a pass and does NOT go in either ledger — keep the
  strategy file as a WATCH candidate and gather more data/universe. **Strategy 002 is the worked
  example of this**: pooled 2.40 but mean 1.93 / 50% pass, no fold clears, next-open 1.65 → WATCH,
  not ADOPT.

**A note on walk-forward folds:** "positive net edge in every fold" is NOT the bar — the bar is
z_paired. A fold can show a big positive net edge with a *negative* paired z (strategy 002 fold 2:
net +2.46% but z_paired −1.36). That means the fold's gains were market beta on the days it
traded, not selection skill. Read the paired z per fold, not the net-edge sign.

When in doubt between ADOPT and anything else, it is not ADOPT.

---

## Sanity checks before you believe your own harness

- Run `python backtest_engine.py` and `python data_loader.py` — both must self-check green.
- Your random control should show ~0% edge vs itself and a z_paired near 0. If your control looks
  like it has an edge, your control is built wrong.
- If a result is "too good" (z_paired > 6, net edge > 3%/trade on a liquid universe), assume a
  look-ahead bug first and go find it. Real daily-bar edges are small.
