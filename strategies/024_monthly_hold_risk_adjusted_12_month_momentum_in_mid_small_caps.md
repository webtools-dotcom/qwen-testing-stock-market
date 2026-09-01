# Strategy 024 — Monthly-Hold Risk-Adjusted 12-Month Momentum in Mid/Small Caps

**Status:** **PROVISIONAL PASS — WATCH, forward-test pending** (2026-08-23). All nine pre-registered kills passed; withheld from ADOPTED.md only on METHODOLOGY §9. Logged to neither ledger.
**Date started:** 2026-08-23

## What this is, and what it is not
Strategy 022's signal at a **21-session (monthly) holding period** instead of 8. 022 established
that the *selection* works (stable mean z_paired +3.90, 10 of 10 calendar years positive, fold
spread tighter than chance, survives vol/beta-matched control, DSR 1.0) but that at an 8-session
hold the round-trip cost consumes the edge: a real portfolio returned +8.49% a year against
+17.21% for simply buy-and-holding the same universe. This tests whether the same signal is
economically viable once turnover is cut.

**Why 21 sessions and not 40.** A holding-period sweep (5, 8, 10, 15, 21, 30, 40, 60, 90, 120)
showed net-of-cost edge per session peaking around 40 with a broad plateau from 30 to 60
(+0.0251 / +0.0271 / +0.0267 per session — statistically indistinguishable). **21 is deliberately
NOT the crest.** It is the canonical monthly-rebalance implementation of 12-month momentum from the
literature, so it is pre-specified by convention and carries **no search penalty**, whereas 40 is
the best of ten horizons I tried and carries the full penalty. Picking 40 here would repeat the
exact error that killed strategy 020. The plateau at 15/30 is a robustness check, not the headline.

## Hypothesis
Liquid Indian mid/small caps are under-covered and re-rate slowly. The measured decay curve says
the edge keeps accumulating with holding period (+0.43% at 8 sessions → +0.93% at 21 → +2.05% at
60) while the edge *per session* falls monotonically (0.053 → 0.044 → 0.034). Against a fixed
~0.45% round-trip cost this implies a break-even hold of roughly **24 sessions** and a viable
region well beyond it. A monthly hold should therefore convert a real-but-unharvestable selection
edge into a tradeable one.

## The enemies, stated first
1. **Survivorship, and it gets WORSE at this horizon.** The universe is a today-list of NSE names;
   a 12-month winner that later collapsed and delisted is absent. A 21-session forward return is
   more exposed to that than an 8-session one, and the fix that makes the strategy viable is the
   same one that amplifies the bias I cannot remove. Hence kill #3 — the survivorship subgroup must
   clear on its own, not merely lean positive.
2. **Horizon shopping.** Ten horizons were measured before this test. Hence kill #8 (deflation) and
   the choice of 21 over the sweep crest.
3. **Beta in disguise.** Longer holds accumulate more market exposure. Hence kill #5.
4. It remains a textbook factor. A pass means "a standard factor is harvestable on liquid NSE
   mid/smalls at a monthly hold", not a discovery.

## Rules (pre-committed, unchanged from 022 except the hold)
- **Universe:** NSE names not in the Nifty 50; 60-day median turnover ≥ ₹25 cr.
- **Signal (close of day t):** `score = change_252d / vol60` — 252-session return divided by
  60-session daily-return standard deviation — in the **top decile** cross-sectionally among
  liquid mid/smalls that day.
- **No other filter.**
- **Entry fill:** same close. **Exit:** time exit at **21 sessions**, no ATR bracket. The control
  receives the identical exit rule.
- **Overlap:** none. **Costs:** charged, liquidity-tiered.

## Kill criteria — decided BEFORE the run
REJECT if any of these:
1. Stable mean z_paired (20 seeds) < 2.0 pooled **or** < 2.0 on the hold-out half of names.
2. Day edge ≤ 0 in any of the three regime blocks (2016-2020 / 2021-2023 / 2024-2026).
3. **Survivorship:** the pre-2017-listed subgroup must itself clear stable mean z_paired ≥ 2.0
   **and** retain ≥ 60% of the pooled day_edge. If most of the edge lives in later listings, the
   result is a listing artifact and this dies.
4. **The tool test — the one that killed the 8-session version.** A 20-position equal-weight
   portfolio, cash-constrained, costs charged, must beat **buy-and-hold of the same universe** on
   CAGR, and must beat a random-selection portfolio run through identical machinery. Losing to
   buy-and-hold means there is no reason to trade it, whatever the z-score says.
5. Dies against a volatility/beta-matched control.
6. Collapses at next-session entry.
7. Fold instability: the five chronological partitions of the paired series must all be positive,
   with spread no greater than the homogeneity randomisation predicts.
8. Deflated Sharpe fails once the ten-horizon search is counted.
9. Not robust to ±1 step in holding period (15 and 30 sessions must lean the same way).

## Search context (§9, honest)
This is the continuation of the largest search in this repo: 24 screening candidates, 4 scaffolded
strategies (020, 021, 023 rejected; 022 the parent), a 60-feature scan on 5 years, a ~2,000-combo
pair scan, a 60-feature × 6-cell scan on 10 years, 21 delivery hypotheses, and a 10-point horizon
sweep. The only defences against that are the pre-specified horizon, the hold-out half, the
survivorship subgroup, and the portfolio test — all of which are kill criteria above.

## Results — all nine pre-registered kills PASSED

### Kills 1, 9, 2 — significance, plateau, regimes
| test | n | paired days | stable mean_z | pass | day_edge | net/trade (ctrl) |
|---|---|---|---|---|---|---|
| **pooled h=21** | 3029 | 1552 | **+3.57** | 100% | +0.984% | +1.997% (+0.964%) |
| hold-out half of names (B) | 1619 | 1067 | **+2.63** | 95% | +1.018% | +2.195% (+1.183%) |
| hold = 15 | 3918 | 1738 | +3.02 | 100% | +0.662% | +1.262% |
| hold = 30 | 2327 | 1344 | +2.55 | 90% | +1.143% | +2.722% |
| P1 2016-2020 | 588 | 407 | +2.24 | 80% | +0.876% | +1.114% |
| P2 2021-2023 | 975 | 526 | +1.60 | 20% | +0.686% | +3.036% |
| P3 2024-2026 | 1443 | 560 | +1.64 | 0% | +0.632% | +1.605% |

All three regime blocks positive on day_edge (kill 2 met); the 15/21/30 plateau all clear 2.0.

### Kill 3 — survivorship, the enemy flagged hardest. Neutralised.
| subgroup | n | mean_z | pass | day_edge |
|---|---|---|---|---|
| **pre-2017 listings only (462 names)** | 2221 | **+2.90** | 100% | **+0.998%** |
| later listings only (167 names) | 808 | +3.13 | 90% | +2.141% |

The pre-2017 subgroup **retains 101% of the pooled day_edge** and clears the bar on its own. The
edge is not a listing artifact. (At the 8-session horizon on the smaller panel this split was
+0.241% vs +0.746% — the concern was real then and is absent here.)

### Kills 5, 6, 8 — controls and deflation
- vol/beta-matched control: **+3.90** (100% pass) — stronger than the random control, so not a
  leverage bet.
- next-session entry: **+3.16** (100% pass) — not fill-fragile.
- Deflated Sharpe against all ten horizons tried: observed SR 0.494 vs a noise ceiling of 0.157,
  **DSR 1.0**. The horizon search is not what produced this.

### Kill 7 — fold stability
Fold z on the realised paired series: **+2.45, +0.26, +2.29, +0.68, +2.28** (all positive), mean
1.59 against a homogeneous expectation of 1.52; spread 1.04 vs 0.93 under randomisation, with 37%
of shuffles at least as dispersed — not significantly unstable, but looser than 022's was.
Per calendar year, **10 of 10 positive** (weakest 2018 +0.041%, strongest 2017 +8.93%).

### Kill 4 — the tool test that killed the 8-session version
20 equal-weight positions, cash-constrained, costs charged:

| portfolio | CAGR | max DD | Sharpe |
|---|---|---|---|
| **strategy, 21-session holds** | **+19.07%** | **−42.4%** | **0.94** |
| buy-and-hold same universe (cost-free) | +17.21% | −54.3% | 0.87 |
| **Nifty Midcap 50 (real investable benchmark)** | +18.43% | −49.1% | — |
| random selection, identical machinery (3 seeds) | +3.5% to +6.9% | −56 to −66% | 0.27-0.43 |

It beats buy-and-hold and a real midcap index on return *and* drawdown, and beats random selection
at identical turnover by 12-15pp a year. Excluding the 252-session warm-up (the signal cannot fire
until Nov 2017), the gap widens: from 2018, **+19.13% vs +13.66%** buy-and-hold and +15.01% for
Midcap 50; from 2019, **+24.88% vs +18.34% / +18.99%**.

## The two fragilities that keep this out of ADOPTED.md
Both were found by attacking the result after it passed, not before.

**1. The tool advantage is cost-fragile.** Breakeven against buy-and-hold sits at roughly a 0.70%
round trip:

| round trip | 0.50% (engine) | 0.60% | 0.70% | 0.80% | 1.00% |
|---|---|---|---|---|---|
| strategy CAGR | +19.07% | +17.89% | +16.72% | +15.56% | +13.27% |
| vs buy-and-hold +17.21% | beats | beats | **loses** | loses | loses |

METHODOLOGY's own stated range for a mid/small round trip is **0.4-1.3%**. The engine model sits at
0.50%, the low end. So the *statistical* edge survives any cost assumption, but the *reason to
trade it instead of an index fund* only survives in the cheaper third of that range. Anyone
implementing this must measure their real slippage before believing the CAGR gap.

**2. The outperformance is concentrated.** Excess over buy-and-hold by year:
2023 +22.4, 2026 +19.2, 2020 +9.4, 2019 +7.5, 2025 +5.8, 2018 +0.0, 2024 −1.3, 2022 −3.4,
2016 −4.2, 2021 −4.8, 2017 −27.1.
Two years carry it. Excluding 2017 as warm-up, total excess is +50.7pp over nine years, of which
the best two supply +41.7pp — leaving about **+1pp a year** from the other seven. The
*selection* edge is broad (10/10 years positive on the paired series); the *portfolio
outperformance* is not.

## Verdict — **PROVISIONAL PASS. WATCH, forward-test pending. Logged to neither ledger.**

This is the strongest candidate this repo has produced: every one of nine pre-registered kill
criteria passed, including the two designed to be lethal — the survivorship subgroup clears alone
while retaining 101% of the edge, and the portfolio beats both buy-and-hold and a real midcap
index on return and drawdown simultaneously. The vol/beta-matched control makes it *stronger*, not
weaker. The search behind it deflates to DSR 1.0.

It is nevertheless **not** written into ADOPTED.md, for one reason and one reason only:
**METHODOLOGY §9 requires an out-of-sample forward test for a candidate that emerged from a large
multi-strategy search, and this is the winner of the largest search in this repo** — 24 screening
candidates, four scaffolded strategies, a 60-feature scan, a ~2,000-combo pair scan, a 6-cell
10-year scan, 21 delivery hypotheses and a 10-point horizon sweep. Every hold-out I have (name
half, regime block, survivorship subgroup) is a *retrospective* hold-out drawn from data the search
could see. The one check a large search cannot fake is time it has not seen, and that check does
not exist yet.

Two supporting reasons to wait rather than adopt: the tool advantage dies above a 0.70% round trip,
and the portfolio outperformance rests on two calendar years.

**Path to a real ADOPT:** run the signal forward on unseen months and compare realised results
against the +0.98%/21-session paired edge and the ~+19% CAGR claim. Nothing else in this dataset
can resolve it. Per AGENTS.md, when in doubt between ADOPT and anything else, it is not ADOPT.
