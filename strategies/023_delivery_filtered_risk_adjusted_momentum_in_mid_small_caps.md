# Strategy 023 — Delivery-Filtered Risk-Adjusted Momentum in Mid/Small Caps

**Status:** REJECTED 2026-08-23
**Date started:** 2026-08-23

## What is new here: data, not arithmetic
Every candidate in this session hit the same ceiling — daily OHLCV in a ~550-name liquid NSE
universe supports cross-sectional edges of only ~0.4%/8 sessions, and the day-clustered statistic
is breadth-limited on top of that. So this candidate brings **information the repo has never had**:

**NSE security-wise delivery data**, pulled from NSE's own archives for 10 years (2,495 sessions):
`sec_bhavdata_full_*.csv` for 2019-07 onward and `MTO_*.DAT` before that.
- `DELIV_PER` — the share of a session's traded quantity actually **taken to demat** rather than
  squared off intraday. This is a direct read on whether buying was positional or speculative, it
  is specific to the Indian market, and **it cannot be derived from price and volume.**
- `NO_OF_TRADES` → average ticket size (a block-activity proxy, 2019+ only).

**Look-ahead discipline — the thing that decides whether any of this is real.** NSE publishes the
delivery file only *after* the session settles; it is not on the tape at that session's close. So
every delivery field is **lagged one full session** before use, enforced once in
`scratch/deliv_lab.py::add_delivery_features` so no strategy can get it wrong. A signal evaluated
at the close of day *t* sees delivery only through day *t−1*.

## What the delivery pre-screen actually found (before this strategy was written)
Run on 452,832 liquid mid/small name-days, 532 names, in the 6-cell frame (2 name-halves × 3
regimes), day-demeaned 8-session forward returns:

**Every long-side delivery hypothesis failed**, including the one with the best prior:
| hypothesis | edge | t |
|---|---|---|
| high delivery % (top decile) | +0.062% | +1.64 |
| delivery surprise `dp_z > 1.5` | +0.055% | +0.97 |
| accumulation: `dp_z>1.5 & ret1>0` | +0.073% | +0.92 |
| **absorption: `dp_z>1.5 & ret5<0`** (best a priori) | +0.007% | **+0.10** |
| block ticket size `ticket_z > 2` | −0.129% | −1.50 |

**The signal is on the short side, and it is strong:**
| hypothesis | edge | t | cells |
|---|---|---|---|
| **`dp_z < −1.5`** (delivery far below the stock's *own* norm) | **−0.476%** | **−7.08** | 5/6 sign |
| delivery % bottom decile | −0.181% | −3.50 | 6/6 sign |

So low-conviction, churn-dominated trading predicts underperformance, while high delivery predicts
nothing. In a long-only engine that makes delivery an **exclusion filter**, which is what this
strategy tests.

Note *which* construction works: the **own-norm z-score** (`dp_z`), not the absolute level and not
the cross-sectional rank (`dp<20%` and `dp` bottom-decile exclusions barely help). Different stocks
have structurally different delivery levels because they have different holder bases, so a change
against the stock's own baseline is the meaningful quantity. That is a mechanism, not a fit.

## Rules (pre-committed)
Identical to 022 in every respect, plus one exclusion:
- **Universe:** NSE names not in the Nifty 50, 60-day median turnover ≥ ₹25 cr.
- **Signal (close of day t):** `score = change_252d / vol60` in the top cross-sectional decile
  among liquid mid/smalls.
- **NEW — delivery exclusion:** skip the name if `dp_z < −1.0`, i.e. its delivery percentage
  (lagged one session) is more than one sigma below its own trailing 60-session norm. The −1.0
  cut is pre-committed as "one sigma"; the gradient is reported as robustness.
  A name with *missing* delivery data is **not** excluded — otherwise the filter would silently
  delete history rather than select on it.
- **Entry fill:** same close. **Exit:** time exit at 8 sessions, no ATR bracket, control identical.
- **Overlap:** none. **Costs:** charged, liquidity-tiered.

## Kill criteria — decided BEFORE the engine run
1. It must **beat 022 head to head** on the same panel (pooled stable mean_z and day_edge). A
   filter that costs more breadth than it adds edge is not an improvement — that is exactly why
   the cross-sectional and absolute-level variants were rejected at pre-screen.
2. Stable mean z_paired ≥ 2.0 pooled **and** on the hold-out half of names.
3. Positive day edge in all three regime blocks.
4. Survives the vol/beta-matched control and next-session entry.
5. The filter threshold must show a **gradient, not a spike** (−1.5 / −1.0 / −0.5 / 0.0 must move
   monotonically, as they did in the pre-screen: t +10.12 / +10.40 / +11.01).
6. **The fold question 022 failed:** at least one fold clears 2.0 and the most recent is
   non-negative. Stated honestly in advance — the pre-screen already shows the filter lifts all
   periods roughly uniformly (~10-20%) and does **not** rescue the 2018-2019 window, which stays
   negative (base −0.147%/t−1.12 → filtered −0.166%/t−1.23). **So this is expected to remain
   INCONCLUSIVE on the fold criterion**, and the honest outcome of this run is most likely "a
   better WATCH", not an adoption. It is being run anyway because the delivery channel deserves a
   measured engine verdict for the ledger, and because a WATCH record should describe the best
   version of the candidate.

## Search context (§9)
Everything in 022's search, plus: 21 delivery hypotheses pre-screened, 9 exclusion variants tested.
This is the winner of a large search and is treated as such.

## Results (real engine runs, 585-name panel with delivery merged, time exit, costs charged)

### Kill #1 — head to head on the identical panel. The filter LOSES.
| variant | n | days | stable mean_z | pass | day_edge | net/trade |
|---|---|---|---|---|---|---|
| **022 baseline, filter OFF** | 6315 | 2014 | **+3.07** | 100% | **+0.475%** | +0.754% |
| 023 filter ON, h=8 | 6122 | 2011 | +2.62 | 85% | +0.459% | +0.786% |
| 023 filter ON, h=6 | 7573 | 2082 | +2.30 | 75% | +0.318% | +0.481% |
| 023 filter ON, h=10 | 5165 | 1900 | +1.54 | 10% | +0.359% | +1.129% |

### Kill #5 — the filter-strength gradient is a U-shape, and unfiltered wins
| dp_z floor | none | -1.5 | -1.0 | -0.5 | 0.0 |
|---|---|---|---|---|---|
| stable mean_z | **+3.05** | +2.93 | +2.59 | +2.61 | +2.89 |
| day_edge | +0.475% | +0.473% | +0.459% | +0.489% | +0.550% |

There is no monotone benefit anywhere. Tightening the filter costs more than it adds at every cut.

### Remaining tests
- Hold-out half of names: **+1.88** (35% pass) — below bar (kill #2)
- Regime blocks: P1 +2.47, P2 +2.27, **P3 +1.52** (5% pass)
- vol/beta-matched control +3.07; next-session entry +2.50
- Engine-default ATR bracket: +0.77, **net −0.104%/trade**
- Walk-forward: +0.22, +1.47, +0.99, +1.46, **+2.76** — **1 of 5 folds clears** (kill #6)

## Verdict — **REJECT**

Kill criteria 1, 2, 5 and 6 all fire. The delivery exclusion does not improve strategy 022; on the
identical panel it is strictly worse (mean_z +2.62 vs +3.07, day_edge +0.459% vs +0.475%), and the
filter-strength gradient peaks at *no filter at all*.

### The lesson worth keeping — why a filter that works in a screen does nothing in a backtest
The day-demeaned pre-screen was unambiguous that this filter helps: excluding `dp_z < -1.0` raised
the measured edge from +0.502% to +0.570% (t +9.47 → +10.40, 6/6 cells, monotone in the
threshold). The engine says otherwise, and the reason is **non-overlapping entries**:

> In a cross-sectional screen, excluding a name-day removes a bad observation. In the engine, the
> name is still in the top decile tomorrow and the day after — so the exclusion does not remove
> the trade, it merely **delays entry into the same name by a few sessions**. What the screen
> scores as "bad trades removed" the backtest experiences as "same trades, shifted timing".

Any filter whose signal is short-lived relative to the holding period will behave this way. This
is a general trap and it is now measured, not theorised: a screen-level improvement of +14% in edge
turned into −15% in stable mean_z.

### What the delivery data was still worth
Its one real finding stands on its own and is logged separately: **abnormally low delivery relative
to a stock's own norm predicts underperformance** (`dp_z < -1.5`: day-demeaned −0.476%/8 sessions,
t −7.08, 5/6 cells; hold-out half t −3.46). That is a genuine short-side / risk signal. It is not
usable in this long-only engine, and as a long-side exclusion it fails for the reason above.
Every long-side delivery hypothesis — high delivery, delivery surprise, accumulation, absorption
into weakness, block ticket size — was already dead at pre-screen (best t +1.64).


