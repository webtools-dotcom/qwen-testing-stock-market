# Strategy 020 — Turnover Expansion Attention Drift in Mid/Small Caps

**Status:** REJECTED 2026-08-22
**Date started:** 2026-08-22

## Hypothesis (mechanism first)
Sustained expansion of *rupee turnover* — the last 20 sessions trading well above the stock's own
60-day baseline — marks a liquidity/attention influx into a mid- or small-cap: new holders
building positions, wider coverage, more order flow. Indian mid/smalls are under-covered and
slow to re-price; the influx is not a one-day event but a multi-week process, so the re-pricing
it drives should still have a further 6-10 sessions to run after the expansion is visible.

This is a *cross-sectional selection* claim, not a market-timing one: on any given day, the
mid/small names with the largest turnover expansion should out-return the other mid/smalls that
same day. That is exactly what the day-clustered paired test measures.

**Why it might not be new / might be fake (state the enemy first):**
- It could be plain intermediate momentum in disguise (volume rises when price rises).
- It could be a volatility/beta bet — high-vol names both trade more and drift more in a bull run.
- It could be survivorship: the panel is a TODAY list, so turnover-expanding names that later
  blew up and delisted are absent.
- 5 of the 5 years in the sample are a mid/small bull market.

## Rules (pre-committed)
- **Universe:** NSE mid/small (panel names NOT in Nifty 50), 60-day median turnover ≥ ₹25 cr.
- **Signal (known at the close of day t):** `turn_ratio20 = mean(turnover, 20d) / median(turnover, 60d)`
  in the **top decile cross-sectionally that day**, among liquid mid/smalls.
- **Entry fill:** same close (indicator signal computed from the close — METHODOLOGY §4). A
  next-open variant is also run as an execution-fragility check.
- **Exit:** time exit at 8 sessions; engine's default 2×ATR stop / 2×ATR target.
- **Holding period:** 8 sessions (middle of the 6-10 day band). 6 and 10 reported as sensitivity.
- **Overlap:** none (`allow_overlap=False`). **Costs:** charged, liquidity-tiered.

## Kill criteria — decided BEFORE the run
REJECT if **any** of these:
1. Stable mean z_paired (20 control seeds) **< 2.0 on the mid/small subgroup itself** (§8 —
   the pool is not enough, the tradeable subgroup must clear alone).
2. Day edge ≤ 0 net of costs.
3. The most recent walk-forward fold has a negative paired z.
4. It dies against a **momentum/volatility-matched control** (control drawn the same day from
   names in the same momentum_60d and atr_pct tercile) — that would make it a momentum/vol bet,
   not an attention effect.
5. It is not robust to the selection threshold (top 5% / top 10% / top 20% must all lean the same
   way — a lone spike at one cut is fitting).
6. It does not replicate on an **independent 484-name broad NSE universe**.
7. It fails the **out-of-sample forward window** (2025-07-01 → 2026-08-21), which was held out
   before any of this search began (§9 — this candidate emerged from a scan of ~45 feature
   variants and ~24 signal candidates in this session; the in-sample number alone is not
   trustworthy).

## Search context (§9, honest count)
Candidate signals run through the engine before this one, this session: 24 (batches 1-3).
Feature variants scanned in the cheap day-demeaned diagnostic: 33 features × 2 subgroups, plus
double sorts. All of it confined to data ≤ 2025-06-30; the forward window was never touched.

## Results (all measured, engine runs)

### In-sample (170-name panel, mid/small, to 2025-06-30)
| test | n | paired days | stable mean_z (20 seeds) | pass | day_edge | net/trade |
|---|---|---|---|---|---|---|
| headline h=8, random control | 1923 | 801 | **+2.10** | 65% | +0.399% | +0.199% |
| momentum/vol-MATCHED control (kill 4) | 1923 | 800 | +2.07 | 60% | +0.322% | +0.199% |
| next-session entry (fragility) | 1904 | 798 | +1.74 | 25% | +0.308% | +0.167% |

Threshold gradient (kill 5) - a lone spike at the chosen decile, not a plateau:
top20% +1.09 / top15% +1.46 / **top10% +2.27** / top5% +1.04.
Horizon band: h=6 +1.54, h=8 +2.27, h=10 +2.63.

Walk-forward (kill 3): F1 -0.13, F2 +0.62, F3 +2.53, F4 (most recent) +1.17 with
net/trade -0.286%. Only 1 of 4 folds clears 2.0.

### The decisive kills - independent universe and held-out window
| test | n | mean_z | day_edge | net/trade |
|---|---|---|---|---|
| kill 6: broad 484-name NSE universe, in-sample h=8 | 3827 | **-0.91** | -0.161% | -0.278% |
| kill 6b: only the 316 names never used in the search | 2738 | **-0.91** | -0.212% | -0.486% |
| kill 7: forward window 2025-07-01..2026-08-21, 170-name panel h=8 | 601 | +1.55 | +0.304% | +0.016% |
| kill 7: forward window, broad universe h=8 | 1293 | **-1.45** | -0.339% | -0.606% |

Broad-universe threshold gradient over the full 5y is negative at every cut
(top20% -0.79, top15% -0.43, top10% -1.50, top5% -1.73).

## Verdict — **REJECT**

The in-sample +2.10 was specific to the 130-name mid/small panel the search ran on. On 316 NSE
names that were never part of the search, the sign flips (mean_z -0.91, day_edge -0.212%,
net -0.486%/trade), and the held-out forward window is -1.45 on the broad universe. Kill criteria
5, 6 and 7 all fire; 3 fires in spirit (1 of 4 folds clears).

This is what a search artefact looks like from the inside: a real day-demeaned gradient in the
diagnostic (t +6.2, positive in every year, surviving momentum/vol/beta double sorts, monotone in
holding period) that does not exist outside the sample it was found in. The cheap diagnostic ran
on the same 170 names the engine then tested, so it selected a universe-specific pattern.

Lesson carried forward: run the day-demeaned pre-screen on a HOLD-OUT universe, not only a
hold-out period.
