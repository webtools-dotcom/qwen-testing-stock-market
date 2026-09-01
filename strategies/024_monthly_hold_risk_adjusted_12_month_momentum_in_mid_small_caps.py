"""Strategy 024 - Monthly-Hold Risk-Adjusted 12-Month Momentum in Mid/Small Caps.

022's signal at a 21-session hold. Rules and the nine kill criteria are pre-registered in the .md;
the decisive ones are #3 (survivorship subgroup must clear alone) and #4 (the portfolio must beat
buy-and-hold, which is what killed the 8-session version).

Run:  python strategies/024_monthly_hold_risk_adjusted_12_month_momentum_in_mid_small_caps.py
"""

import sys, os, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch"))

import numpy as np
import pandas as pd
from backtest_engine import (
    day_clustered_edge, stable_day_clustered_z, sharpe, deflated_sharpe,
)

m = importlib.import_module("022_risk_adjusted_12_month_momentum_swing_in_mid_small_caps")
pf = importlib.import_module("022_portfolio")

HOLD = 21                      # pre-committed: monthly, the literature convention. NOT the crest.
P1_END, P2_END = m.P1_END, m.P2_END
LO, HI = m.LO, m.HI


def summarize(label, strat, cf, seeds=20):
    return m.summarize(label, strat, cf, seeds=seeds)


def main():
    panel = m.prepare(m.load("master_10y"))
    names = sorted(panel)
    rng = np.random.default_rng(23)
    A = set(rng.permutation(names)[: len(names) // 2])
    B = set(names) - A
    full = m.slice_panel(panel)
    print(f"universe {len(panel)} names, {len(full)} liquid mid/small, hold={HOLD}\n", flush=True)

    print("== KILL 1: pooled and hold-out half of names ==", flush=True)
    strat, cf = m.run_set(full, horizon=HOLD)
    pooled = summarize(f"pooled h={HOLD}", strat, cf)
    s, c = m.run_set(m.slice_panel(panel, names=B), horizon=HOLD)
    summarize("hold-out half B", s, c)

    print("\n== KILL 9: +/-1 step in holding period ==", flush=True)
    for h in (15, 21, 30):
        s, c = m.run_set(full, horizon=h)
        summarize(f"hold={h}", s, c, seeds=10)

    print("\n== KILL 2: regime blocks ==", flush=True)
    for lbl, lo, hi in (("P1 2016-2020", LO, P1_END), ("P2 2021-2023", P1_END, P2_END),
                        ("P3 2024-2026", P2_END, HI)):
        s, c = m.run_set(m.slice_panel(panel, lo, hi), horizon=HOLD)
        summarize(lbl, s, c)

    print("\n== KILL 3: survivorship - names listed before 2017 must clear ALONE ==", flush=True)
    first = {t: d["date"].min() for t, d in panel.items()}
    old = {t for t, dt in first.items() if dt <= pd.Timestamp("2017-01-01")}
    new = set(panel) - old
    print(f"   {len(old)} pre-2017 names, {len(new)} later listings", flush=True)
    s, c = m.run_set(m.slice_panel(panel, names=old), horizon=HOLD)
    r_old = summarize("pre-2017 names only", s, c)
    s, c = m.run_set(m.slice_panel(panel, names=new), horizon=HOLD)
    summarize("later listings only", s, c)
    if r_old and pooled:
        keep = r_old["dc"]["day_edge"] / pooled["dc"]["day_edge"]
        print(f"   pre-2017 subgroup retains {100*keep:.0f}% of pooled day_edge "
              f"(kill #3 needs >= 60% and z >= 2.0)", flush=True)

    print("\n== KILL 5/6: matched control, next-session entry ==", flush=True)
    s, c = m.run_set(full, horizon=HOLD, matched=True)
    summarize("vol/beta-MATCHED control", s, c)
    s, c = m.run_set(full, horizon=HOLD, next_open=True)
    summarize("next-session entry", s, c)

    print("\n== KILL 7: fold stability on the realised paired series ==", flush=True)
    ctrl = cf(0)
    sser = pd.Series([t["net_pct"] for t in strat],
                     index=[t["entry_date"] for t in strat]).groupby(level=0).mean()
    cser = pd.Series([t["net_pct"] for t in ctrl],
                     index=[t["entry_date"] for t in ctrl]).groupby(level=0).mean()
    paired = (sser - cser).dropna().sort_index()
    z_pool = paired.mean() / (paired.std(ddof=1) / np.sqrt(len(paired)))
    K = 5

    def fold_zs(v):
        out = []
        for ch in np.array_split(np.asarray(v), K):
            if len(ch) > 5 and ch.std(ddof=1) > 0:
                out.append(ch.mean() / (ch.std(ddof=1) / np.sqrt(len(ch))))
        return np.array(out)

    obs = fold_zs(paired.values)
    print(f"   paired days {len(paired)}, pooled z {z_pool:+.2f}", flush=True)
    print(f"   fold z {np.round(obs,2)}  mean {obs.mean():.2f} (homogeneous expectation "
          f"{z_pool/np.sqrt(K):.2f}), spread {obs.std(ddof=1):.2f}", flush=True)
    rr = np.random.default_rng(0)
    sp = np.array([fold_zs(rr.permutation(paired.values)).std(ddof=1) for _ in range(2000)])
    print(f"   spread under homogeneity {sp.mean():.2f}; "
          f"{100*(sp>=obs.std(ddof=1)).mean():.0f}% of shuffles as spread out or more", flush=True)
    print("\n   per calendar year (traded paired series):", flush=True)
    for y, g in paired.groupby(paired.index.year):
        if len(g) < 30:
            continue
        se = g.std(ddof=1) / np.sqrt(len(g))
        print(f"     {y}: edge {g.mean():+.3f}%  z {g.mean()/se:+5.2f}  days {len(g)}", flush=True)

    print("\n== KILL 8: deflated Sharpe against the 10-horizon search ==", flush=True)
    obs_sr = sharpe([t["net_pct"] for t in strat], holding_days=HOLD)
    trials = []
    for h in (5, 8, 10, 15, 21, 30, 40, 60, 90, 120):
        ss, _ = m.run_set(full, horizon=h)
        trials.append(sharpe([t["net_pct"] for t in ss], holding_days=h))
    print(f"   observed SR {obs_sr:.3f}; 10 horizon trials {[round(x,3) for x in trials]}", flush=True)
    print(f"   {deflated_sharpe(obs_sr, trials, n_obs=len(strat))}", flush=True)

    print("\n== KILL 4: THE TOOL TEST - portfolio vs buy-and-hold ==", flush=True)
    df = pf.build_frame(full)
    pf.stats(pf.run_portfolio(df, "benchmark"), "buy-and-hold universe")
    eq_s = pf.run_portfolio(df, "strategy", hold=HOLD)
    pf.stats(eq_s, f"strategy hold={HOLD}")
    rnds = [pf.run_portfolio(df, "random", hold=HOLD, seed=s) for s in range(3)]
    for i, e in enumerate(rnds):
        pf.stats(e, f"random hold={HOLD} seed {i}")
    for cm in (1.5, 2.0):
        pf.stats(pf.run_portfolio(df, "strategy", hold=HOLD, cost_mult=cm), f"strategy costs x{cm}")

    print("\n   per calendar year, strategy vs buy-and-hold:", flush=True)
    be = pf.run_portfolio(df, "benchmark")
    rmean = pd.concat(rnds, axis=1).mean(axis=1)
    for y in sorted(set(eq_s.index.year)):
        a = eq_s[eq_s.index.year == y]; b = be[be.index.year == y]; c = rmean[rmean.index.year == y]
        if len(a) < 20:
            continue
        ra, rb, rc = a.iloc[-1]/a.iloc[0]-1, b.iloc[-1]/b.iloc[0]-1, c.iloc[-1]/c.iloc[0]-1
        print(f"     {y}: strategy {ra*100:+7.2f}%  buy-hold {rb*100:+7.2f}%  random {rc*100:+7.2f}%"
              f"  excess {100*(ra-rb):+7.2f}%", flush=True)


if __name__ == "__main__":
    main()
