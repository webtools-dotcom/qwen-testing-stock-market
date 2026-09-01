"""Master lab: 629-name union universe, 10 years, 6 cells (2 name-halves x 3 regimes)."""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from lab import features, NIFTY_50, MIN_TURNOVER

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, "cache", "_master_flat.pkl")
P1_END = pd.Timestamp("2020-12-31"); P2_END = pd.Timestamp("2023-12-31")

def load_panel():
    o = pickle.load(open(os.path.join(BASE, "cache", "master_10y.pkl"), "rb"))
    return o["data"]

def build(horizons=(6,8,10), force=False):
    if os.path.exists(CACHE) and not force:
        return pickle.load(open(CACHE, "rb"))
    panel = load_panel()
    rets = {}
    for t, df in panel.items():
        s = pd.Series(df["close"].pct_change().values, index=df["date"].values)
        rets[t] = s[~s.index.duplicated()]
    mkt = pd.DataFrame(rets).mean(axis=1).sort_index()
    rows = []
    for t, df in panel.items():
        d = features(df.copy().reset_index(drop=True), mkt)
        for h in horizons:
            d[f"fwd{h}"] = (d["close"].shift(-h) / d["close"] - 1) * 100
        d["ticker"] = t; d["mid_small"] = t not in NIFTY_50
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        rows.append(d)
    flat = pd.concat(rows, ignore_index=True)
    flat = flat[flat["liq"]].copy()
    for h in horizons:
        flat[f"fwd{h}_dm"] = flat[f"fwd{h}"] - flat.groupby("date")[f"fwd{h}"].transform("mean")
    names = sorted(flat["ticker"].unique())
    rng = np.random.default_rng(31)
    a = set(rng.permutation(names)[: len(names)//2])
    flat["half"] = np.where(flat["ticker"].isin(a), "A", "B")
    flat["period"] = np.where(flat["date"] <= P1_END, "P1",
                       np.where(flat["date"] <= P2_END, "P2", "P3"))
    pickle.dump(flat, open(CACHE, "wb"))
    return flat

def dayt(sub, col="fwd8_dm"):
    s = sub.dropna(subset=[col])
    if len(s) < 60: return (np.nan, np.nan, 0)
    d = s.groupby("date")[col].mean()
    if len(d) < 10: return (np.nan, np.nan, len(d))
    return (d.mean(), d.mean()/(d.std(ddof=1)/np.sqrt(len(d))), len(d))

CELLS = [(h,p) for h in ("A","B") for p in ("P1","P2","P3")]

def report(name, sel, col="fwd8_dm"):
    m, t, nd = dayt(sel, col)
    cs = [dayt(sel[(sel.half==h)&(sel.period==p)], col)[1] for h,p in CELLS]
    agree = sum(1 for x in cs if np.isfinite(x) and np.sign(x)==np.sign(t) and abs(x)>=1.5)
    same = sum(1 for x in cs if np.isfinite(x) and np.sign(x)==np.sign(t))
    cstr = " ".join(f"{h}{p}{x:+5.2f}" if np.isfinite(x) else f"{h}{p}   --" for (h,p),x in zip(CELLS,cs))
    return (f"{name:34s} n={len(sel):6d} days={nd:4d} edge={m:+.3f}% t={t:+5.2f} "
            f"[{same}/6 sign, {agree}/6 at1.5] {cstr}")
