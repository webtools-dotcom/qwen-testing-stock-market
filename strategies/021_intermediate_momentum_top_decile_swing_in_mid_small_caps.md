# Strategy 021 — Intermediate Momentum Top Decile Swing in Mid/Small Caps

**Status:** REJECTED 2026-08-22
**Date started:** 2026-08-22

## Relationship to REJECTED.md — declared up front
Two existing rejections are adjacent and this must be read against them:
- **"Intermediate Momentum (126-21) Pullback to 50 SMA"** — same underlying factor, but that test
  required a *pullback entry* to the 50 SMA and a **20-day hold**. It died (stable mean_z −1.11).
- **"Relative Strength Rotation vs Nifty Quartile Acceleration"** — RS vs the index with an
  acceleration overlay (stable mean_z 1.99).
- **"Low-Vol High-RS Compounder Breakout"** and **"Momentum-breakout / VCP swing"** — momentum
  with a *breakout/consolidation* entry trigger.

What is different here: **no entry trigger at all.** The claim under test is that the plain
cross-sectional factor works *without* the pullback / breakout / acceleration timing layers, and
that those layers were what killed the earlier versions. The diagnostic already supports that
reading — adding a pullback filter ("below sma_20") gives S +0.666%/t+4.97 in the search half but
**−0.303%/t−2.21 in the hold-out half** and −0.119% forward. The overlays were the overfit.
If this fails too, the factor itself is dead in this universe and the whole family closes.

## Hypothesis (mechanism)
Indian mid/small caps are under-covered and slowly re-priced. A stock that has out-returned its
peers over the last ~6 months, *excluding the most recent month* (so the measure is not the
short-term reversal effect in disguise), is in a re-rating that institutions build into over
weeks. Holding 6-10 sessions harvests a slice of that drift. The claim is purely
**cross-sectional selection**: on any given day, the top-decile names beat the other liquid
mid/smalls that same day — which is precisely what the day-clustered paired test measures.

**Why it might be fake (the enemies):**
- Momentum is a beta/volatility bet in a bull market — the sample is 5 mid/small bull years.
- Survivorship: a TODAY list excludes momentum names that later collapsed and delisted. This is
  the single biggest unfixable caveat here, and it biases momentum specifically.
- Momentum crashes: the diagnostic already shows **2025 was −0.893%/day, t −4.57** — a full year
  of factor inversion. Any adoption must carry that.
- It is a textbook factor, not a discovery. If it passes, the honest claim is "the standard
  cross-sectional momentum factor survives honest testing on liquid NSE mid/smalls at a 6-10 day
  horizon", not "a new edge".

## Rules (pre-committed)
- **Universe:** NSE names not in the Nifty 50 ("mid/small"), 60-day median turnover ≥ ₹25 cr.
- **Signal (known at the close of day t):** `mom = ret120 − ret20`, i.e. the 120-session return
  excluding the most recent 20 sessions (the standard "12-2"/"126-21" intermediate-momentum
  construction, pre-committed from the literature — not tuned here). Enter if `mom` is in the
  **top decile cross-sectionally among liquid mid/smalls that day**.
- **No other filter.** No pullback, no breakout, no RSI, no slope condition. (Every such overlay
  tested in the diagnostic degraded the hold-out half.)
- **Entry fill:** same close (indicator signal from the close — METHODOLOGY §4). Next-session
  entry is run as an execution-fragility check.
- **Exit:** 8 sessions, engine default 2×ATR stop / 2×ATR target. 6 and 10 reported.
- **Overlap:** none. **Costs:** charged, liquidity-tiered.

## Kill criteria — decided BEFORE the engine run
REJECT if **any** of these:
1. Stable mean z_paired (20 seeds) < 2.0 **on the hold-out half of names** (half B, in-sample
   dates). The search half alone proves nothing — this is the check that killed strategy 020.
2. Stable mean z_paired < 2.0 on the **held-out forward window** (2025-07-01 → 2026-08-21).
3. Day edge ≤ 0 net of costs on either hold-out set.
4. It dies against a **volatility/beta-matched control** (same day, same atr_pct and beta
   tercile) — that would make it a leverage bet, not a selection edge.
5. No decile gradient: D8/D9/D10 must lean the same way in all three sets (a lone D10 spike is
   fitting).
6. It only survives on same-close fills and collapses at next-session entry.
7. The most recent walk-forward fold is significantly negative.

## Search context (§9, honest count)
This session, before this candidate: 24 signal candidates through the engine (batches 1-3), one
full strategy tested and rejected (020), plus a 60-feature × 2-decile day-demeaned scan. Crucially
**this candidate was selected on half A of the names and the pre-2025-07 period only**; half B of
the names and the forward window were never used to choose it, and both are kill criteria above.

## Results (real engine runs, 484-name NSE panel)

Two exit specifications were run. The engine default (2xATR stop / 2xATR target) and a time-exit
spec (hold to the horizon, no bracket) - the latter declared before its numbers were seen, because
a 2xATR target caps the right-skewed payoff a drift hypothesis depends on. Control gets the
identical exit rule in both.

**Engine-default bracket exit:** dead on arrival - even the SEARCH half is stable mean_z -0.50
(day_edge -0.179%, net -0.109%/trade). The ATR bracket plus costs is a heavier tax than the edge.

**Time exit, h=8:**
| set | n | paired days | stable mean_z | pass | day_edge | net/trade (ctrl) |
|---|---|---|---|---|---|---|
| search half A, in-sample | 1413 | 683 | +1.62 | 20% | +0.325% | +0.457% (+0.121%) |
| **KILL 1: hold-out half B, in-sample** | 1279 | 664 | **+0.60** | 0% | +0.261% | +0.382% (+0.177%) |
| **KILL 2: forward window, all names** | 981 | 272 | **+0.76** | 0% | +0.146% | +0.054% (-0.109%) |
| KILL 2: forward window, half B only | 459 | 224 | +0.60 | 0% | +0.248% | +0.163% (-0.248%) |
| pooled full sample (all names, all dates) | 3698 | 1080 | **+2.36** | 100% | +0.347% | +0.342% (+0.064%) |
| vol/beta-MATCHED control, full sample | 3698 | 1078 | +2.42 | 100% | +0.389% | +0.342% (+0.092%) |
| next-session entry, full sample | 3694 | 1079 | +2.36 | 100% | +0.356% | +0.364% (+0.064%) |

Forward window by horizon: h=6 +1.30, h=8 +0.76, h=10 +1.96 (30% pass).

Decile gradient (full sample, time exit) is real and monotone: D10 +2.36, D9 +1.30, D8 -0.86,
D5 -2.75, D1 -1.66.

Walk-forward (time exit): F1 +1.30, F2 +0.58, **F3 (2024-08..2025-08) -1.16** (day_edge -0.359%,
net -1.178%) - the momentum crash the diagnostic flagged as 2025 t -4.57.

## The trap this candidate demonstrates
The **pooled** full-sample number is stable mean_z **+2.36 at a 100% pass rate**, survives a
vol/beta-matched control at +2.42, survives next-session entry at +2.36, and sits on a clean
monotone decile gradient. Read on its own it looks like a clear ADOPT. It is not: the
pre-registered hold-out half of NAMES is +0.60 and the held-out forward window is +0.76. The
pooled significance is METHODOLOGY 8 power-from-combining, not signal.

## Verdict - **REJECT**

Kill criteria 1, 2, 3 (forward net/trade +0.054% is effectively nil) and 7 all fire. The factor is
directionally real - the decile ladder is monotone in every split, and the day-demeaned diagnostic
is positive in the search half, the hold-out half and the forward window - but it is **too weak to
clear the bar out-of-sample once trades are non-overlapping and costs are charged**. Under the
engine's default ATR bracket it is negative outright.

Measured calibration worth carrying forward: a day-demeaned diagnostic of t +4.79 on a name set
translates to an engine stable mean_z of only **+1.62** on that same set, because non-overlap turns
26,830 eligible name-days into 1,413 trades (~2 entries per day, so each day's strategy mean is an
average of ~2 names instead of ~20). **A candidate needs a hold-out diagnostic of roughly t >= 6
before it has any chance of clearing engine mean_z 2.0.**

This closes the momentum family in this universe: the plain factor fails here, and the earlier
pullback/breakout/acceleration overlays (see the REJECTED rows named at the top of this file)
failed harder.
