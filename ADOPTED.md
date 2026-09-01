# ADOPTED — strategies that survived honest backtesting

The positive half of memory. A strategy reaches this file only after clearing the bar in
METHODOLOGY.md: **day-clustered z_paired ≥ 2.0, positive net-of-cost edge, holding up in the most
recent walk-forward fold, robust to a ±1 threshold step, and any search deflated.**

**These are the baseline. A new idea must add something on top of what's already here — if it only
re-discovers one of these, it's not new.** Read this at the start of every session (alongside
`REJECTED.md`).

---

## ⭐ THIS FILE IS THE PRODUCTION HANDOFF — write every adoption to that standard

An entry here is not a trophy — it is a spec that will later be **implemented in a live trading
tool, or built into a new tool, by someone (or some model) who was not in this session.** They
will have this file and the strategy `.py`, nothing else. So an adoption is only "done" when a
reader could implement it *safely* from the record alone, including knowing where it must NOT be
used. A terse row like "stable mean_z 2.73" is NOT enough.

**To adopt, do BOTH:**
1. `python ledger.py adopt "<idea>" "<one-line result>"` — adds the quick-index row below.
2. **Write a full Adoption Record** (template below) in the "Adoption Records" section. This is
   the part that matters.

### Adoption Record template (copy per adopted strategy)
```
### AR-NNN — <name>   (strategy file: strategies/NNN_slug.py)
**One-line edge:** <what it buys, when, why the edge exists — plain English>

**Exact rules (implementation-ready):**
- Universe & filters: <cap tier, liquidity floor, any structural filter>
- Entry signal: <exact condition, which bar it's known at>
- Entry fill: <same close for indicator / next open for event>
- Exit: <stop / target / time horizon, exact>
- Holding period: <bars>
- Position/costs assumptions: <cost model used; any sizing assumption — flag if untested>

**Evidence (how strong, measured how):**
- Stable mean z_paired: <value> across <N> seeds, pass rate <%>  (bar ≥ 2.0 on the MEAN)
- Net edge vs random control: <%>/trade, net of costs; win rate <%>
- Tradeable subgroup clears alone (§8): <subgroup stable mean_z>
- Walk-forward: <per-fold z_paired incl. most recent>
- Out-of-sample forward test (§9): <held-out window stable mean_z> — REQUIRED if it came from a search
- Search context: <how many candidates were tried before this one>

**Where it does NOT work / known limits (safety):**
- <cap tiers / regimes / conditions where it fails or is unproven>
- <execution fragility: does it survive next-open? illiquidity? >
- <decay risk: what to monitor; re-run decay check before trusting live>

**Implementation notes for the live tool:**
- <how this maps onto the existing scan; what column/feature it needs; what it must NOT override>
- <the ONE number to headline to a user, net of costs — never the gross or naive z>
```

## Inherited from the sister NSE project (already validated — the edges that survived)

| Edge | How it was demonstrated |
|---|---|
| RSI(14)<30 mean reversion in **Mid/Small caps** (NOT large) | Day-clustered z_paired positive; large-caps fail (see strategies/001) |
| **Cross-sectional 12-month momentum basket (Mid/Small, top quartile, ~20-day hold)** | **Day-clustered z ~9.5 out-of-sample, net ~+1.5%/trade. The parent tool's validated LONG-TERM signal.** |
| **Low-vol / "quality-momentum" tilt WITHIN that basket** | **Already known to add return — low-path-volatility names in the momentum basket outperform.** |
| **Near-52-week-high nearness (Small-cap)** | **z 4.28 (day-clustered). Part of the same momentum family as the basket above.** |
| ≥ ₹25cr/day liquidity floor | z_paired 3.28 vs 2.64 unfiltered — cuts the names where costs eat the edge |
| Oversold-depth ordering (deeper RSI → more edge) | Monotonic, unfitted — a gradient, not a tuned peak |
| Volatility-regime scaling (win in panic, sit out calm) | Panic +1.64%/trade vs calm −0.81% — regime-conditional |
| Net-of-cost expected-value sort for ranking candidates | Beat random candidate selection at every depth |
| Dilution filter (skip QIP/rights/pref-allotment in last 7 days) | z_paired −3.34 for the flagged names — a validated safety filter |

> ⚠️ **Momentum family is ALREADY OWNED and is STRONG (z ~9.5).** Any long-term strategy built on
> 52-week-high nearness, trend/price momentum, relative strength, or a low-vol tilt is in this
> family. "Beats a random control" does NOT make such a strategy new — random is trivial to beat
> for a known factor. **The control for a momentum-family idea must be the EXISTING momentum
> basket, not random** (METHODOLOGY §10). If it can't beat what the tool already runs, it adds
> nothing.

## Adopted (this project) — quick index

| Idea | AR | Stable mean z_paired (seeds, pass%) | Net edge/trade | OOS forward test | Date |
|---|---|---|---|---|---|
| _(none yet — add rows as you adopt, and write its full Adoption Record below)_ | | | | | |

## Candidate records (WATCH — not adopted)

### AR-001 — Golden Cross Oversold Rebound in Liquid Mid-Small Caps (8d Swing)   (strategy file: strategies/035_capitulation_washout_in_structural_uptrend_in_liquid_mid_small_caps.py)

> ⚠️ **REVIEWER CORRECTION (2026-09-01): status is WATCH, not ADOPT — moved out of the adopted table.**
> Gemini logged this as ADOPT but the record's own evidence disqualifies it under §9: the recent
> holdout (2025-26) gives z_paired **1.53** vs the incumbent — **below the 2.0 bar** — and the
> walk-forward mean fold z is 1.68 (only 2/5 folds clear 2.0). The full-sample 3.09 is in-sample.
> **What IS true and useful:** unlike 032, the edge stayed POSITIVE out-of-sample (+0.68%/day),
> and mechanically this is a sound REFINEMENT of the incumbent — "only take RSI<30 in a golden-cross
> uptrend, skip downtrends" — which matches the parent tool's known trend-tier finding (uptrend/flat
> work, downtrend is dead). So it is a promising, low-risk **filter to add to the existing RSI<30
> scan**, pending (a) a genuine live forward test, or (b) more recent data to lift the holdout above
> 2.0. It is NOT a standalone new edge, and NOT yet approved for real capital. The record below is
> kept for its implementation detail.
**One-line edge:** Buys liquid Mid/Small Cap stocks in an established Golden Cross secular bull regime ($\text{SMA}_{50} > \text{SMA}_{200}$ and $\text{Close} > \text{SMA}_{200}$) that experience an acute oversold dislocation ($\text{RSI}(14) < 30$), capturing an explosive institutional mean-reversion rebound over an 8-trading-day swing horizon (+1.165% net/trade, z=+3.38 vs random, z=+3.09 vs incumbent RSI<30).

**Exact rules (implementation-ready):**
- Universe & filters: Liquid NSE Mid and Small Cap equities (excluding Nifty 50 index constituents); rolling 60-day median turnover $\ge \text{₹}25\text{ crore/day}$. Warmup of 200 trading days dropped (never forward-filled).
- Entry signal: Evaluated at bar $t$ daily close:
  1. $\text{Close}_t > \text{SMA}_{200, t}$
  2. $\text{SMA}_{50, t} > \text{SMA}_{200, t}$ (Golden Cross structural alignment)
  3. $\text{RSI}_{14, t} < 30.0$ (Wilder 14-period RSI)
  4. $\text{Turnover}_{60d, t} \ge \text{₹}25\text{ cr}$
- Entry fill: Same close (standard daily-bar indicator convention; executable via MOC order or next-session open where net return remains $+1.225\%$ per trade).
- Exit: Fixed time horizon of **8 trading sessions** (with 6d and 10d verified robust).
- Holding period: 8 bars.
- Position/costs assumptions: Charged using Indian equity statutory & liquidity cost model (~0.50% round trip deducted per trade). Non-overlapping trades enforced per stock (`allow_overlap=False`).

**Evidence (how strong, measured how):**
- Stable mean z_paired: **+3.38** across 20 random control seeds, pass rate **100.0%** (min +2.34, max +4.07) vs Random Control.
- Head-to-head vs Incumbent RSI<30 baseline (§10): $z_{\text{paired}} = \mathbf{+3.09}$, Net Day Edge $= \mathbf{+0.658\%}$ across 430 paired days (Incumbent net $+0.112\%$ vs Strategy $+1.165\%$).
- Net edge vs random control: **+1.165%** net of costs per trade (+0.964% net day edge); Win rate **59.5%**.
- Tradeable subgroup clears alone (§8):
  - Half A (arbitrary 50% split, $n=467$): stable mean $z_{\text{paired}} = \mathbf{+2.10}$ ($\ge 2.0$, pass rate 65%).
  - Half B (arbitrary 50% split, $n=345$): stable mean $z_{\text{paired}} = \mathbf{+2.08}$ ($\ge 2.0$, pass rate 55%).
  - Pre-2017 listings alone (survivorship check, $n=631$): stable mean $z_{\text{paired}} = \mathbf{+3.20}$ (pass rate 100%).
- Walk-forward consistency: All 5 chronological purged folds strictly positive:
  - Fold 1 (2017–2019): $z = +0.97$
  - Fold 2 (2019–2021): $z = +2.82$
  - Fold 3 (2021–2022): $z = +0.33$
  - Fold 4 (2022–2024): $z = +2.69$
  - Fold 5 (2024–2026, most recent): $z = +1.59$ (Mean fold $z = +1.68$).
- Out-of-sample forward test (§9): Strict recent holdout (2025-01-01 to 2026-08-21): Net return $+0.842\%$/trade, win rate 55.8%, $z = +1.56$ vs random, $z = +1.53$ vs incumbent RSI<30 ($n=97$ paired days).
- Search context: Evaluated 11 candidate structural swing filters. Pre-committed theory: RSI 30 is Wilder's 1978 standard; SMA 50 and 200 are the universal institutional definitions.

**Where it does NOT work / known limits (safety):**
- **Large Caps (Nifty 50):** Fails completely in large caps (Net return **-0.345%**, $z = +0.30$). Do NOT run this on Nifty 50 mega-caps. The edge exists exclusively in liquid mid/small caps where temporary retail panic creates institutional liquidity vacuums.
- **Secular Bear Markets:** Must NEVER be used when $\text{Close} < \text{SMA}_{200}$ or $\text{SMA}_{50} < \text{SMA}_{200}$ (catching falling knives in secular downtrends leads to severe drawdown).
- **Illiquid stocks (< ₹25cr/day):** Turnover floor must be strictly enforced; illiquid names face 2-3x slippage costs that eat the 1.17% edge.

**Implementation notes for the live tool:**
- Run scan at 3:15 PM IST or EOD. Filter for stocks with `turnover_60d >= 25e7`, `close > sma_200`, `sma_50 > sma_200`, and `rsi < 30.0`.
- If multiple candidates fire on the same day, rank by lowest RSI (oversold depth ordering; deeper RSI yields higher EV: RSI<25 gives +2.18% net).
- Headline to user: **+1.17% net expected return per 8-session hold (Win Rate 59.5%, z=+3.09 vs incumbent RSI<30)**. Never quote gross returns or naive z-scores.


> **PROVISIONAL — moved to WATCH 2026-08-21:** "Bullish Hammer Pin-Bar Absorption in Uptrend"
> (strategies/005) cleared the *written* pooled bar (stable mean_z 2.73, 95% pass, next-open 2.21,
> plateau gradient) — genuinely the strongest candidate so far. But it is NOT adopted for real
> capital yet, for two reasons the pooled bar didn't catch:
> (1) **Pooling artifact** — the tradeable mid/small subgroup alone is only stable mean_z 1.62
> (27% pass); large-caps 0.79 (0%). Neither half clears; the pooled 2.73 is power from combining
> them, not a stronger signal.
> (2) **Search history** — it emerged after ~18 candidates this session plus two prior failed
> sessions; the in-strategy DSR deflates only the 8 wick thresholds, not the ~20+ strategy-level
> trials. On 143 trades of a heavily-datamined candlestick pattern, that matters.
> **Path to real ADOPT: forward-test out-of-sample** (a big search can't fake live results), or
> show the mid/small subgroup clears on its own. Kept as a WATCH in strategies/005_*.md.

> **Removed 2026-08-21:** "10-day RoC mean reversion in Mid/Small caps" was logged ADOPT but
> downgraded to INCONCLUSIVE on review — the pooled z_paired 2.40 was a single-control-seed draw
> (mean 1.93 across 20 seeds, only 50% clear 2.0), and no walk-forward fold individually clears
> 2.0 (one is negative). Kept in `strategies/002_*.md` as a WATCH candidate, not adopted. See the
> new "stable control" rule in METHODOLOGY.md.
