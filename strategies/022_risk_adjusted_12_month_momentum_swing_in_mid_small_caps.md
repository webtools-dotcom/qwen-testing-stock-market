# Strategy 022 — Risk-Adjusted 12-Month Momentum Swing in Mid/Small Caps

**Status:** WATCH (updated 2026-08-23) — selection edge CONFIRMED and fold concern RETRACTED, but **not viable as a 6-10 day tool on cost grounds**. Logged to neither ledger.
**Date started:** 2026-08-22

## Family overlap — declared before anything else
This is a **momentum-family** candidate, and the family has a long rejection history in this repo:
021 (plain 120d-ex-20d momentum, plain top decile), "Intermediate Momentum (126-21) Pullback to
50 SMA", "Momentum-breakout / VCP swing", "Low-Vol High-RS Compounder Breakout", "Relative
Strength Rotation vs Nifty Quartile Acceleration". **021's verdict text even said the family was
closed in this universe.** So this candidate does not get the benefit of the doubt; it gets a
harder bar than the standard one (below).

Two things are materially different, and they are the only reasons this is being run at all:
1. **The construction is different and untested:** the score is divided by trailing volatility.
   Every rejected version selected on raw return, which in this universe collapses into "buy the
   highest-volatility names" — the exact failure mode flagged in REJECTED (`atr_pct` and `beta`
   deciles carry a large part of the raw-momentum spread in a bull run). Dividing by vol is a
   different selection, not a reparametrisation of the same one.
2. **The evidence base is different:** 10 years (2016-11 → 2026-08, 2,222 trading days, 443 liquid
   names) instead of 5, including the 2018-19 small-cap bear and the COVID crash — regimes no run
   in this repo has ever seen. 021 died on a 5-year window where the hold-out half diagnostic was
   only t +2.06; here the same hold-out-half construction is t +8.06.

If this fails, the momentum family is closed for good and should not be reopened without new data
(intraday, delivery volumes, or a point-in-time universe).

## Hypothesis (mechanism)
Liquid Indian mid/small caps are under-covered; a re-rating that has been running for a year is
absorbed slowly, and the next 6-10 sessions inherit a slice of it. Dividing the 12-month return by
recent volatility ranks stocks by the *quality* of the trend rather than its raw size, which
should (a) avoid the lottery/high-beta names that make raw momentum a leverage bet, and (b) reduce
exposure to momentum crashes.

**Why it might be fake — the enemies, stated first:**
- **Survivorship, and it is worst exactly here.** The universe is a TODAY list of NSE names. A
  12-month-momentum screen selects past winners, and the losers that were delisted over the last
  decade are simply absent from the panel. This is unfixable with this data and gets stated in the
  verdict whatever the result.
- Momentum is a beta/vol bet in a bull sample → hence kill #5, the vol/beta-matched control.
- Momentum crashes: measured per-year, 2019 (−0.12%), 2023 (−0.07%) and 2025 (−0.14%) are
  flat-to-negative for this signal family. Any adoption must carry that.
- It is a textbook factor. If it passes, the honest claim is "a standard factor survives honest
  testing on liquid NSE mid/smalls at a 6-10 day horizon", not "a discovery".

## Rules (pre-committed)
- **Universe:** NSE names not in the Nifty 50, 60-day median turnover ≥ ₹25 cr.
- **Signal (known at the close of day t):** `score = change_252d / vol60`, where `change_252d` is
  the 252-session % return and `vol60` is the 60-session daily-return standard deviation in %.
  Enter if `score` is in the **top decile cross-sectionally among liquid mid/smalls that day**.
- **No other filter.** (Every overlay tested in the diagnostic degraded the hold-out sets.)
- **Entry fill:** same close (indicator computed from the close — METHODOLOGY §4). Next-session
  entry is a kill criterion, not a footnote.
- **Exit — declared before the run:** hold to the horizon, **no ATR bracket**
  (`stop_atr_mult=target_atr_mult=99`). Reason, pre-stated: a 2×ATR target truncates the
  right-skewed payoff a drift hypothesis depends on, and 021 measured that it turns the same
  signal from +1.62 to −0.50. **The control is given the identical exit rule**, so the comparison
  is fair. The engine-default bracket is also reported.
- **Horizon:** 8 sessions headline; 6 and 10 reported.
- **Overlap:** none. **Costs:** charged, liquidity-tiered.

## Kill criteria — decided BEFORE the engine run (harder than the standard bar)
REJECT if **any** of these:
1. Stable mean z_paired (20 seeds) **< 2.0 on the hold-out half of names (half B) alone**.
2. Stable mean z_paired < 2.0 pooled.
3. **< 2.0 on the 2016-2020 block (P1) alone** — the regime block no prior run in this repo has
   touched, and the one containing a bear market. A factor that only works after 2021 is a
   bull-market artifact.
4. Day edge ≤ 0 net of costs in any of the three period blocks.
5. It dies against a **volatility/beta-matched control** (same day, same atr_pct and beta
   tercile). This is the leverage-bet test and it is the one this family most deserves.
6. It collapses at next-session entry (stable mean_z < 2.0 there).
7. No decile gradient: D10 > D9 > D8 must hold and D1 must be negative.
8. The most recent walk-forward fold is significantly negative.
9. Large caps show the *same* edge — that would mean it is not the under-coverage mechanism
   claimed, just a factor premium (recorded as a caveat, not an automatic kill).

## Search context (§9, honest count)
This session: 24 screening candidates through the engine, 2 full strategies scaffolded and
rejected (020 turnover expansion, 021 plain intermediate momentum), 1 idea killed at the
pre-screen and logged (macro-shock beta lead-lag), a 60-feature × 2-decile scan on 5 years, a
~2,000-combo pair scan, and a 60-feature × 2-decile × 6-cell scan on 10 years. **This candidate is
the winner of a large search and must be treated as such** — which is why kills 1 and 3 require it
to stand up on a name set and a regime block that the search did not choose it on.

## Results (real engine runs, 487-name 10y NSE panel, time exit, costs charged)

### Headline and the hold-outs
| test | n | paired days | stable mean_z (20 seeds) | pass | day_edge | net/trade (ctrl) |
|---|---|---|---|---|---|---|
| pooled h=6 | 6738 | 2044 | +2.90 | 100% | +0.331% | +0.170% (-0.088%) |
| **pooled h=8** | 5428 | 1954 | **+3.09** | 100% | +0.414% | +0.425% (+0.045%) |
| pooled h=10 | 4563 | 1868 | +2.98 | 100% | +0.487% | +0.615% (+0.182%) |
| KILL 1: hold-out half B (never searched) | 2701 | 1468 | **+2.15** | 75% | +0.376% | +0.361% (+0.134%) |
| half A (searched) | 2727 | 1477 | +2.95 | 95% | +0.618% | +0.489% (+0.045%) |
| KILL 5: vol/beta-MATCHED control | 5428 | 1955 | +3.56 | 100% | +0.413% | +0.425% (+0.079%) |
| KILL 6: next-session entry | 5424 | 1954 | +2.75 | 95% | +0.359% | +0.439% (+0.045%) |
| KILL 9: large caps (placebo) | 1273 | 902 | +0.36 | 0% | +0.039% | +0.069% (+0.185%) |

### Regime blocks (KILL 3/4)
| block | n | mean_z | pass | day_edge | net/trade |
|---|---|---|---|---|---|
| P1 2016-2020 (never seen in this repo before) | 1136 | +2.30 | 75% | +0.495% | +0.316% |
| P2 2021-2023 | 1839 | +1.76 | 20% | +0.378% | +0.894% |
| **P3 2024-2026 (most recent)** | 2424 | **+0.67** | 0% | +0.166% | +0.146% |
| P1 x hold-out half B (hardest cell) | 561 | +1.80 | 30% | +0.568% | +0.346% |

### Threshold robustness (KILL 7) — a plateau, and it exposes the real constraint
Inclusive cuts, all with essentially the same edge: top5% +2.24 (edge +0.434%), top10% +3.05
(+0.414%), top15% **+3.71** (+0.427%), top20% +2.37 (+0.246%). Adjacent-decile buckets:
D10 +3.05, D9 +0.79, D8 +0.43, D5 -1.36, D1 -1.72.
Note top15% scores *higher* than top10% at the same edge size — the z is breadth-limited, not
edge-limited (see below).

### Walk-forward (KILL 8) — the finding that decides this
| fold | mean_z | pass | day_edge | net/trade |
|---|---|---|---|---|
| 1  2018-04..2019-12 | +1.28 | 0% | +0.550% | -0.342% |
| 2  2019-12..2021-08 | +0.30 | 0% | +0.097% | +1.134% |
| 3  2021-08..2023-04 | +1.04 | 0% | +0.406% | -0.043% |
| 4  2023-04..2024-12 | +0.51 | 0% | +0.102% | +1.086% |
| 5  2024-12..2026-08 | +0.71 | 0% | +0.146% | +0.055% |

**No fold clears 2.0. None even reaches 1.3.** The pooled +3.09 is 10 years of accumulation.

### Survivorship probe — the finding that makes it worse
Splitting the panel by when a name enters it:
- names present from 2016-17 (380 names): mean_z +2.18, day_edge **+0.241%**, net +0.229%
- names that listed later (107 names): mean_z +3.07, day_edge **+0.746%**, net +1.009%

Most of the edge sits in recently-listed names - exactly where the TODAY-list bias is strongest,
because a post-2017 listing that collapsed and delisted is not in this panel at all. The
subgroup that is *least* contaminated has an edge of +0.241%/8 sessions against a round-trip cost
stack of roughly 0.45%.

### Engine-default ATR bracket
mean_z +0.68, **net -0.162%/trade** - under 2xATR stop/target the strategy loses money. The edge
exists only under a pure time exit (which was pre-declared, with the control given the same rule).

## Verdict — **INCONCLUSIVE / WATCH.** Not adopted. Logged to neither ledger.

It clears the written kill criteria 1-7 and 9: pooled +3.09 at a 100% pass rate, hold-out half of
names +2.15, the never-before-tested 2016-2020 block +2.30, a vol/beta-matched control that makes
it *stronger* (+3.56, so it is not a leverage bet), next-session entry +2.75 (not fill-fragile), a
genuine threshold plateau, and a large-cap placebo that is dead (+0.36) as the under-coverage
mechanism predicts.

It is still not an adoption, for three reasons:
1. **No walk-forward fold individually clears the bar** (best +1.28, most recent +0.71). Under
   METHODOLOGY that is the definition of INCONCLUSIVE, and strategy 002 is the worked example.
   The pooled significance is 10 years of accumulation, not a per-period edge.
2. **The most recent regime block is +0.67 with 0% pass** — whatever is there has been weak for
   the last two and a half years.
3. **The survivorship split is damning.** Two-thirds of the edge is carried by names that listed
   after 2017; the least-contaminated subgroup has +0.241%/trade against a ~0.45% cost stack.

Kept as a WATCH. What would settle it: a point-in-time universe including delisted names (kills
or confirms the survivorship explanation), which this data source cannot provide.

**Open thread taken up next:** the top-15% cut scoring higher than top-10% at an identical edge
shows the statistic is **breadth-limited** — with 443 names the top decile yields only ~2
non-overlapping entries per day, so each day's strategy mean is an average of ~2 stocks. The same
rules on the full liquid NSE universe are tested next, with the prediction stated in advance: if
the effect is real, day_edge stays near +0.4% while per-fold z rises toward 2.0; if day_edge
collapses, the effect was specific to this 487-name panel.

---

## Follow-up run: the 629-name master universe (full liquid NSE, 10y)

The breadth prediction stated above was tested by rebuilding the universe from NSE's official
EQUITY_L list (2,291 EQ symbols; **only 507 clear the ₹25cr liquidity floor** — so the liquid NSE
universe really is ~500-600 names, and breadth cannot be bought). Union with the earlier panel =
629 names, 579 liquid mid/smalls. **Rules unchanged.**

**The prediction held.** day_edge stayed put (+0.525% vs +0.414%) while breadth and z rose:

| test | n | days | stable mean_z | pass | day_edge | net/trade (ctrl) |
|---|---|---|---|---|---|---|
| master pooled h=8 (3.15 entries/day) | 6373 | 2022 | **+3.90** | 100% | +0.525% | +0.446% (+0.028%) |
| 142 names never used in any search | 1393 | 755 | +1.42 | 30% | +0.438% | +0.307% (+0.057%) |
| P1 2016-2020 | 1261 | 663 | +2.41 | 85% | +0.669% | +0.130% |
| P2 2021-2023 | 2049 | 696 | +1.91 | 45% | +0.377% | +0.797% |
| **P3 2024-2026** (was +0.67 on the small panel) | 3031 | 639 | **+2.03** | 60% | +0.425% | +0.344% |
| **old names only (462 listed pre-2017)** | 4641 | 1938 | **+3.04** | 100% | +0.417% | +0.296% |

Walk-forward, master universe: F1 +0.77, F2 +0.82, F3 +1.04, F4 +1.28, **F5 (2024-12..2026-08)
+2.78 (100% pass)**. Old-names-only folds: +0.18, +1.32, **-0.01**, +1.02, +2.22.

**Search deflation (§6/§9):** observed SR 0.291 vs a noise ceiling of 0.087 across 7 threshold
trials → **DSR 1.0**. The threshold search is not what is producing this.

**Survivorship re-checked:** on the small panel two-thirds of the edge sat in post-2017 listings.
On the master universe that mostly disappears — the 462 pre-2017 names carry +0.417% day_edge
against +0.525% pooled. Listing bias is a real but secondary contributor, not the explanation.

**Day-demeaned diagnostic on the master universe (breadth-independent):** edge +0.425%, t +8.40,
and **all 6 of the 6 name-half × regime cells agree in sign at |t| ≥ 1.5**
(AP1 +2.67, AP2 +5.61, AP3 +4.44, BP1 +3.59, BP2 +5.24, BP3 +3.46). This is the most homogeneous
signal measured in this session by a wide margin.

**Factor-timing overlay — tested and killed.** Gating entries on the factor's own trailing 60-day
return (a series constructed with no forward information) does not help: gate-on edge +0.360%
(t +5.58) vs **gate-off +0.457% (t +5.82)**. Consistent with every other overlay tried on this
family — the plain factor is the robust object.

### Why this is still NOT an adoption
The effect is directionally consistent everywhere (day_edge positive in all ~25 slices measured,
ranging +0.27% to +0.67%) and its *significance* is limited by universe size, not by instability.
But the bar is the bar:
- **4 of 5 walk-forward folds do not clear 2.0**, and on the least-survivorship-contaminated
  subgroup two folds are effectively zero (+0.18 and −0.01). A spec handed to production must not
  have two multi-year windows with no measurable edge.
- The cleanest out-of-sample name set (142 never-searched names) is +1.42, below bar — underpowered
  rather than contradictory, but it does not confirm either.
- It sits in a family with a long rejection history here, behind the largest search in this repo.
- Under the engine's default ATR bracket it loses money; the edge is exit-spec dependent.

**Status: WATCH.** What would settle it, in order: (1) a genuine forward test on live months;
(2) a point-in-time universe including delisted names; (3) nothing else — more in-sample slicing
cannot resolve this, and per METHODOLOGY §9 a borderline winner-of-many is exactly the case where
only out-of-sample time counts.

---

# 2026-08-23 follow-up: two corrections and the decisive economic test

## Correction 1 — the "no fold clears" finding was my own measurement artifact
The earlier walk-forward re-ran the whole simulation *inside* each ~400-day window. That restarts
the 252-session momentum warmup and the non-overlap state at every fold boundary, destroying
trades and depressing fold z. **Strategy 022 fits no parameters** (the signal and the decile cut
are pre-committed), so there is no train/test leakage to purge against — the correct way to test
period stability is to partition the realised day-level paired differences.

Done properly, on 2,022 paired days (pooled z +3.96):

| fold | window | day_edge | 95% CI | z |
|---|---|---|---|---|
| 1 | 2017-08..2019-09 | +0.892% | ±0.729 | +2.40 |
| 2 | 2019-09..2021-08 | +0.383% | ±0.702 | +1.07 |
| 3 | 2021-08..2023-05 | +0.477% | ±0.563 | +1.66 |
| 4 | 2023-05..2024-12 | +0.385% | ±0.434 | +1.74 |
| 5 | 2024-12..2026-08 | +0.487% | ±0.400 | +2.39 |

All five positive, edges tightly clustered. Randomisation test (4,000 shuffles of the paired
series, which imposes homogeneity by construction):
- expected per-fold z if homogeneous = 3.96/√5 = **1.77**; observed mean = **1.85**
- observed fold-z spread **0.56** vs **0.91** under homogeneity — the periods are *less* dispersed
  than chance. A regime break would show the opposite.
- P(≤1 fold clears 2.0 | homogeneous effect of exactly this size) = **21.6%**. Even the old number
  was unremarkable.

**Per calendar year on the traded paired series: 10 of 10 years positive** — 2017 +3.70%,
2018 +0.21%, 2019 +0.47%, 2020 +0.58%, 2021 +0.48%, 2022 +0.34%, 2023 +0.52%, 2024 +0.26%,
2025 +0.15%, 2026 +1.01%. The earlier "2018-19 is edgeless" claim came from the day-demeaned
screen of all eligible name-days, which is a different population from the trades actually taken.

**The stability objection is withdrawn. The selection edge is real and homogeneous.**

## Correction 2 — but the paired test never asked whether this is worth trading
Portfolio simulation: 20 equal-weight concurrent positions, 8-session holds, cash-constrained,
liquidity-tiered round-trip costs, 579 names, ~10 years.

| portfolio | CAGR | max DD | Sharpe | final |
|---|---|---|---|---|
| **strategy 022 (8-day holds)** | **+8.49%** | −45.5% | 0.51 | 2.21x |
| random selection, same machinery (5 seeds) | −5.9% to +1.7% | ~−67% | ~0.0 | ~0.8x |
| **equal-weight universe, buy and hold** | **+17.21%** | −54.3% | 0.87 | 4.70x |

Selection skill is unambiguous — it beats random selection run through identical machinery by
~11 percentage points a year. **And it still loses to doing nothing but holding the universe.**
Excess return vs the universe is negative in 9 of 11 calendar years.

The arithmetic: a round trip costs ~0.45%, and an 8-session hold means ~31 round trips per slot
per year ≈ **14% a year of cost drag**. The selection edge is ~+0.5% per 8 sessions. The edge pays
for the trading and almost nothing else. Cost sensitivity confirms how thin the margin is:
at 1.5× costs CAGR falls to +1.88%, at 2× costs to −4.33%.

## The finding that matters: the edge is real, the *horizon* is wrong
Holding-period sweep, same portfolio machinery:

| hold | CAGR | max DD | Sharpe |
|---|---|---|---|
| 8 sessions (the swing window) | +8.49% | −45.5% | 0.51 |
| 15 | +15.84% | −44.1% | 0.83 |
| 25 | +17.21% | −42.5% | 0.86 |
| **40** | **+23.01%** | **−43.1%** | **1.08** |
| 60 | +16.61% | −42.3% | 0.83 |
| *equal-weight universe* | *+17.21%* | *−54.3%* | *0.87* |
| *random selection at 60-day holds* | *+14.78%* | −49.9% | 0.78 |

At ~40 sessions it beats buy-and-hold on return, drawdown and Sharpe simultaneously, and it still
beats random selection at the same turnover — so it is selection, not merely less churn.

**This is a lead, not a result.** 40 is the best of five holding periods tried, which is exactly the
threshold-fitting trap in METHODOLOGY §6; it carries no deflation, no hold-out, and no
pre-registration. It also sits outside the 6-10 day swing brief this work was commissioned under.

## Verdict — **WATCH, and REJECTED for the 6-10 day swing use case**
As a 6-10 day swing tool: **no.** The selection edge is genuine and statistically solid, but it is
smaller than the turnover cost required to harvest it, and the resulting portfolio loses to simply
holding the universe. That is a cost-economics rejection, not a statistical one, and no amount of
further slicing changes it.

The open thread is now a *different* strategy: the same signal at a ~1-2 month horizon. That needs
its own pre-registered test with the holding period committed in advance, deflated for the sweep
above, and validated on a name set and period the sweep did not choose it on.
