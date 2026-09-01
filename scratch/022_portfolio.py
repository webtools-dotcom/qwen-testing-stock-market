"""Portfolio-level simulation of strategy 022 - the 'can this be a tool' question.

The day-clustered paired test measures per-trade SELECTION SKILL. It says nothing about whether an
actual portfolio built on the signal is worth running. Those are different questions and this file
answers the second one, honestly:

  * equal-weight portfolio, at most K concurrent positions, each held exactly 8 sessions
  * a position is only opened with cash actually free that day (no infinite capital)
  * round-trip costs charged per position, liquidity-tiered, same model as the engine
  * compared against BOTH: (a) the equal-weight liquid mid/small universe (the honest benchmark -
    this is the beta the strategy is drawn from) and (b) a random-selection portfolio run through
    the IDENTICAL machinery, which is the control that tells you whether selection did anything

Everything here includes market beta by construction, so the strategy-vs-benchmark gap is the
number that matters, not the strategy's own CAGR.
"""
import sys, os, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategies"))
import numpy as np, pandas as pd
from backtest_engine import round_trip_cost_pct

m = importlib.import_module("022_risk_adjusted_12_month_momentum_swing_in_mid_small_caps")

HOLD = 8
K = 20                       # concurrent positions


def build_frame(panel):
    keep = ["date", "ticker", "close", "rank", "liq", "turnover_60d"]
    df = pd.concat([d[keep] for d in panel.values()], ignore_index=True)
    return df.sort_values(["date", "ticker"])


def run_portfolio(df, mode="strategy", k=K, hold=HOLD, seed=0, cost_mult=1.0):
    """Returns a daily equity series. mode: 'strategy' | 'random' | 'benchmark'."""
    df = df[df["liq"]].copy()
    dates = np.sort(df["date"].unique())
    px = df.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    rk = df.pivot_table(index="date", columns="ticker", values="rank", aggfunc="last")
    to = df.pivot_table(index="date", columns="ticker", values="turnover_60d", aggfunc="last")
    # pivot_table drops all-NaN rows, so rank/turnover can be missing dates price has
    dates = px.index.values
    rk = rk.reindex(px.index)
    to = to.reindex(px.index)
    ret = px.pct_change()
    rng = np.random.default_rng(seed)

    if mode == "benchmark":
        eq = (1 + ret.mean(axis=1).fillna(0)).cumprod()
        return eq

    equity = 1.0
    curve = {}
    open_pos = {}                     # ticker -> (days_left, weight_value)
    for i, dt in enumerate(dates):
        # mark existing positions to market
        if open_pos:
            r = ret.loc[dt]
            for t in list(open_pos):
                d_left, val = open_pos[t]
                rr = r.get(t, np.nan)
                val = val * (1 + (0.0 if not np.isfinite(rr) else rr))
                d_left -= 1
                if d_left <= 0:
                    equity += val               # position closed, cash returns to the pot
                    del open_pos[t]
                else:
                    open_pos[t] = (d_left, val)
        # open new positions with free slots
        slots = k - len(open_pos)
        if slots > 0 and i < len(dates) - hold - 1:
            row = rk.loc[dt]
            if mode == "strategy":
                cand = row[(row >= 0.90)].index.tolist()
            else:
                cand = row[row.notna()].index.tolist()
                rng.shuffle(cand)
            cand = [t for t in cand if t not in open_pos and np.isfinite(px.loc[dt].get(t, np.nan))]
            take = cand[:slots] if mode == "strategy" else cand[:slots]
            if take:
                per = equity / max(1, slots) if equity > 0 else 0.0
                per = min(per, equity / max(1, len(take))) if len(take) else 0.0
                for t in take:
                    if equity <= 0:
                        break
                    cost = round_trip_cost_pct(to.loc[dt].get(t, np.nan)) * cost_mult / 100.0
                    stake = min(per, equity)
                    equity -= stake
                    open_pos[t] = (hold, stake * (1 - cost))
        curve[dt] = equity + sum(v for _, v in open_pos.values())
    return pd.Series(curve)


def stats(eq, name):
    r = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0
    print(f"  {name:26s} CAGR {cagr*100:+6.2f}%  maxDD {dd*100:6.1f}%  Sharpe {sh:5.2f}  "
          f"final {eq.iloc[-1]:.2f}x")
    return {"cagr": cagr, "dd": dd, "sharpe": sh, "eq": eq}


if __name__ == "__main__":
    panel = m.prepare(m.load("master_10y"))
    full = m.slice_panel(panel)
    df = build_frame(full)
    print(f"universe {len(full)} names, {df.date.nunique()} dates\n", flush=True)

    print(f"=== portfolio: {K} concurrent positions, {HOLD}-session holds, costs charged ===",
          flush=True)
    res = {}
    res["strategy"] = stats(run_portfolio(df, "strategy"), "strategy 022")
    rnd = [run_portfolio(df, "random", seed=s) for s in range(5)]
    for i, e in enumerate(rnd):
        stats(e, f"random control seed {i}")
    res["bench"] = stats(run_portfolio(df, "benchmark"), "equal-weight universe")

    print("\n=== per calendar year: strategy vs equal-weight universe ===", flush=True)
    se = res["strategy"]["eq"]; be = res["bench"]["eq"]
    rand_mean = pd.concat(rnd, axis=1).mean(axis=1)
    for y in sorted(set(se.index.year)):
        a = se[se.index.year == y]; b = be[be.index.year == y]; c = rand_mean[rand_mean.index.year == y]
        if len(a) < 20:
            continue
        ra = a.iloc[-1] / a.iloc[0] - 1
        rb = b.iloc[-1] / b.iloc[0] - 1
        rc = c.iloc[-1] / c.iloc[0] - 1
        print(f"  {y}: strategy {ra*100:+7.2f}%   universe {rb*100:+7.2f}%   random-pf {rc*100:+7.2f}%"
              f"   excess vs universe {100*(ra-rb):+7.2f}%")

    print("\n=== cost sensitivity (strategy CAGR) ===", flush=True)
    for cm in (1.0, 1.5, 2.0):
        e = run_portfolio(df, "strategy", cost_mult=cm)
        stats(e, f"costs x{cm}")

    print("\n=== position-count sensitivity ===", flush=True)
    for k in (10, 20, 30):
        e = run_portfolio(df, "strategy", k=k)
        stats(e, f"K={k}")

    print("\n=== holding-period sweep: does a longer hold beat buy-and-hold? ===", flush=True)
    bench = run_portfolio(df, "benchmark")
    stats(bench, "equal-weight universe")
    for h in (8, 15, 25, 40, 60):
        e = run_portfolio(df, "strategy", hold=h)
        stats(e, f"strategy hold={h}d")
    for h in (25, 60):
        e = run_portfolio(df, "random", hold=h, seed=0)
        stats(e, f"random hold={h}d")
