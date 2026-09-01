# Strategy 019 — Sector Leader Lead-Lag Catch-Up

Pre-registration written BEFORE any number was computed. Results section filled after.

---

## Hypothesis
Information diffuses **gradually across firms within an industry**: the most-traded (highest
turnover) names in a sector are analysed and repriced first, while under-covered followers in the
same sector lag and catch up over the following 1-2 weeks (Hou 2007, *Industry Information
Diffusion and the Lead-Lag Effect*; Lo–MacKinlay 1990 cross-autocorrelation). India should be a
favourable venue for this: mid/small caps are retail-dominated, thinly covered by sell-side, and
sector news (a cement price hike, a pharma USFDA cycle, a bank NIM print) is genuinely common to
the group. So: when a sector's **leader basket** has moved up over the last week and a liquid
**non-leader** in the same sector has NOT followed, buy the laggard for a 6-10 day swing.

Why it might be fake — stated up front: "leader up, follower flat/down" is mechanically correlated
with "follower had a low 5-day return", i.e. plain short-term reversal, which this repo has already
half-tested (strategy 002, WATCH at mean_z 1.93). It is also correlated with "the sector is hot",
i.e. sector beta over the holding window. Both must be controlled for, not assumed away.

## Checked against REJECTED.md?
- [x] Not present. Nearest neighbours checked:
  - *Relative Strength Rotation vs Nifty Quartile Acceleration* (009, rejected) — buys **strength**
    vs the **index**; this buys **weakness** vs a **sector cohort**. Opposite sign, different
    reference set.
  - *Resilient Relative Strength in Market Pullback* (017, rejected) — buys the name holding up
    while the market falls; this buys the name that failed to rise while its peers rose.
  - *Short-term reversal as an extra filter on RSI<30* (inherited reject) — that was reversal
    stacked on RSI<30. Here reversal is the **confound to be killed**, and a reversal-matched
    control is a pre-registered kill test.
  - *10-day RoC mean reversion* (002, WATCH) — unconditional own-return reversal, no sector
    conditioning. The whole claim of 019 is that the sector-relative part adds something; kill
    test 4 measures exactly that and rejects the strategy if it does not.

## Rules (exact, unambiguous)
- **Universe:** ~150 NSE names with a hand-assigned static sector tag (16 sectors), 5y daily bars,
  liquidity floor `turnover_60d ≥ ₹25cr/day` (the ADOPTED-validated floor). Survivorship: the
  universe is today's listed names — delisted failures are excluded. Stated as a caveat; the
  liquid large/mid NSE space had few delistings in 2021-26 but the bias direction is optimistic.
  Sector tags are today's classification (stable over the window, but not point-in-time).
- **Leader basket (point-in-time, no look-ahead):** on each bar, the 3 names in the sector with the
  highest `turnover_60d` **as of that bar** (a trailing 60-day median, known at the close).
- **L5** = equal-weight 5-day log return of that day's leader basket (excluding the candidate).
- **F5** = the candidate's own 5-day log return. **GAP = L5 − F5.**
- **Entry signal (all known at the close of bar t):**
  1. Candidate is **not** in its sector's leader basket on bar t.
  2. Sector leader basket is moving: `L5 > 0` **and** the sector is in the **top third of sectors
     that day** ranked by L5.
  3. `GAP` is in the **top decile cross-sectionally** among liquid non-leader names that day.
  4. `turnover_60d ≥ ₹25cr`.
  Decile / tercile cut-offs are conventions carried over from the cross-sectional asset-pricing
  literature (and from strategy 018 in this repo), not values tuned on this data. Sensitivity to
  ±1 step is checked anyway.
- **Entry fill:** same close (pure daily-bar indicator signal, §4 convention). Next-open fill is
  run as a fragility check.
- **Exit:** engine defaults — 2.0×ATR stop, 2.0×ATR target, otherwise time exit. Honest gap fills.
- **Holding period:** 8 bars (middle of the requested 6-10 day band); the whole 6→10 band is
  reported.
- **Costs:** `charge_costs=True`, liquidity-tiered. `allow_overlap=False`.

## Kill criteria — decided NOW, before any number
1. **Stable mean z_paired < 2.0** across 20 control seeds → REJECT.
2. **Net edge ≤ 0** after costs → REJECT.
3. **§8 subgroup:** the mid/small (non-Nifty-50) half must clear ≥ 2.0 **on its own**. A pooled
   pass carried by combining two failing halves → REJECT.
4. **Reversal-matched control:** control drawn on the same days from names matched on the
   candidate's own 5-day-return quintile but WITHOUT the sector-leader condition. If the edge vs
   this control is not clearly positive, the signal is just short-term reversal in a costume →
   REJECT.
5. **Sector-day-matched control:** control drawn on the same days from other liquid non-leader
   names **in the same sector**. If the edge vs this control dies, it is hot-sector beta, not
   laggard selection → REJECT.
6. **No gradient:** if GAP deciles show a lone spike in D10 rather than a monotone/plateau
   gradient → REJECT (fitted, not mechanistic).
7. **Recent fold:** negative paired z in the most recent walk-forward fold → REJECT.
8. **Execution:** if it only survives at same-close fill and dies at next-open → at best
   INCONCLUSIVE, never ADOPT.

## Threshold handling
- [x] Pre-committed conventions (top decile GAP, top tercile sector, 3-name leader basket, 8-day
      hold). Sensitivity to ±1 step reported; no threshold was chosen after seeing a result.

## Search context (§9)
This is the **only** candidate tested in this session — one pre-registered idea, no sweep across
strategy variants. Prior sessions in this repo have burned ~20+ candidates (see REJECTED.md), so
the repo-level multiple-testing burden is real and a borderline pass here would still be a WATCH,
not an ADOPT.

---

## Results (after running)

Command run:
```
python strategies/019_sector_leader_lead_lag_catch_up.py       # full log: scratch/019_run1.log
python scratch/019_tight_check.py                              # tightest-cell door-close
```

Panel: 170/174 NSE names, 5y daily (2021-08-23 → 2026-08-21), 16 sectors. 119,389 scored
follower stock-days, 6,782 signal rows over 1,134 days → 2,978 non-overlapping trades.

| Metric | Value |
|---|---|
| Trades (non-overlapping, 8d) | 2,978 |
| Paired days | 1,017 |
| Gross avg/trade | +0.370% |
| Avg round-trip cost | 0.500% |
| **NET avg/trade** | **−0.130%** (random control −0.184%) |
| Net edge vs random control /trade | +0.053% |
| naive z (edge_vs_control) | 0.53 (p=0.60) — optimistic, not the headline |
| DAY-CLUSTERED z_paired (seed 42) | 1.77 |
| **MEAN z_paired, 20 control seeds** | **+1.71** (min +0.65, max +2.56) |
| Pass rate (seeds ≥ 2.0) | **15%** |
| §8 Mid/Small subgroup | mean_z +1.66, pass 25%, net −0.112% |
| §8 Large-cap (N50) subgroup | mean_z +0.67, pass 5%, net −0.294% |
| **vs REVERSAL-matched control** | **mean_z +1.53**, pass 25%, edge +0.129% |
| **vs SECTOR-DAY-matched control** | **mean_z +0.25**, pass 0%, edge +0.046% |
| Per-fold z_paired | F1 +1.18, F2 +0.15, F3 +0.78, F4 (most recent) +1.66 — none clears 2.0 |
| Next-open z_paired | +1.57, pass 25% |
| Robust to ±1 threshold step? | **No** — surface runs 1.33 → 2.96 across the 9 neighbouring cells |
| Holding band 6→10d | 1.96 / 1.80 / 1.68 / 1.41 / 1.82 — dead across the whole swing window |

**GAP decile gradient (within hot sectors) — no mechanism:**

```
D1 z_paired +0.03 | D2 +0.73 | D3 +2.04 | D4 +2.09 | D5 +0.92
D6 +3.60         | D7 −0.49 | D8 +0.60 | D9 +2.32 | D10 (the signal) +1.77
```

If lead-lag catch-up were real, forward return should rise monotonically with GAP — the bigger
the shortfall vs the sector leaders, the more catch-up left. It does not. D6 (a middling gap) is
the strongest cell at +3.60 and D7 right beside it is negative. That is a noise field, not a
gradient. (D1 ≈ 0.03 is also the harness sanity check: the anti-signal extreme sits at zero, as it
should.)

### The decisive test — kill criterion 5
Against a **sector-day-matched control** (same day, same sector, same liquidity screen, other
non-leader names, matched cell counts) the edge is **+0.046%/trade and stable mean_z +0.25, 0% of
20 seeds clearing**. Buying the *laggard* is worth essentially nothing versus buying *any* liquid
non-leader in the same hot sector. The +1.71 vs a random control is therefore hot-sector beta —
the paired test nets out the whole market, but it does not net out the sector, and this signal
selects sectors first. The lead-lag hypothesis (that the specific laggard catches up) is not what
is producing the number.

Kill criterion 4 lands the same way from the other side: against a control matched on the
candidate's own 5-day-return quintile, mean_z is +1.53 (25% pass). What is left after removing
the plain short-term-reversal component does not clear either.

### Bias hunt — what could be faking this?
- **Look-ahead:** none found. `turnover_60d` is a trailing 60-day median and `r5` a trailing
  5-day return, so the leader basket and GAP are both known at the close of the entry bar. Cross-
  sectional ranks use same-day information across stocks only, never future dates. Fill is the
  same close (the §4 indicator convention); next-open re-run gives +1.57, so nothing hinges on the
  fill timing.
- **Overlap:** `allow_overlap=False`; 6,782 signal rows collapse to 2,978 trades.
- **Day-clustering:** headline is z_paired over 1,017 paired days. Naive z 0.53 vs paired 1.77 —
  here the paired number is the *higher* one, which is expected for a signal that fires broadly
  in a market where random entries also lose money; it does not rescue it.
- **Costs:** charged, liquidity-tiered, 0.500% average. The strategy is **net negative in absolute
  terms** (−0.130%/trade). The only "edge" is that random entries lose 0.053% more.
- **Threshold fit:** the pre-committed cell (gap ≥ 0.90, sector tercile ≥ 0.667) gives 1.68. The
  9-cell sensitivity surface runs 1.33 → 2.96, monotone in "be more selective" — the classic
  fewer-days-higher-z artefact already rejected twice in this repo (nominal price, P(win) floor).
  The tightest cell (gap ≥ 0.95, sector ≥ 0.80) reaches mid/small mean_z +2.61 (90% pass) vs a
  random control — the tempting number — but it is n=1,527, **net −0.002%/trade (zero money)**, it
  drops to mean_z +1.75 (25% pass) against the sector-day-matched control, and its neighbour
  (gap ≥ 0.85, same sector cut) collapses to +0.36 against that control. A spike, not a plateau,
  and it makes nothing after costs even where the z looks good. Door closed.
- **Survivorship:** universe is today's listed names (4 tickers failed to download and were
  dropped); bias direction is optimistic and the result is still a reject, so it does not change
  the verdict.
- **Single period:** walk-forward run; no fold clears 2.0 and the second fold is flat (+0.15).

## VERDICT
**REJECT.** Pre-registered pooled stable mean z_paired **+1.71** (15% pass over 20 seeds) against
the 2.0 bar, **net −0.130%/trade after costs**, neither §8 subgroup clears alone (mid/small +1.66,
large +0.67), no walk-forward fold clears 2.0, no GAP decile gradient, and — decisively — the edge
vs a **sector-day-matched control is +0.25 with a 0% pass rate**, meaning the signal is hot-sector
beta rather than laggard catch-up. Dead across the entire 6-10 day band (1.96 / 1.80 / 1.68 /
1.41 / 1.82).

Search context (§9): one pre-registered candidate this session, no variant sweep before the
headline. The 9-cell sensitivity grid was run *after* the verdict was already determined by the
pre-registered cell, and is reported as a fitted surface, not as a result.

If REJECT → added a row to `REJECTED.md`? [x]
