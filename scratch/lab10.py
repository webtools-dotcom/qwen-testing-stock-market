"""Lab v3: same feature engineering, 10-year panel (2016-2026), fresh name split, and three
regime blocks instead of one hold-out period.

Cells: {half A, half B} x {P1 2016-2020, P2 2021-2023, P3 2024-2026}. P1 covers the 2018-19
small-cap bear and the COVID crash - regimes absent from every earlier run in this repo. A
candidate has to work in most cells, not just on average.
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from lab import features, NIFTY_50, MIN_TURNOVER

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, "cache", "_lab10_flat.pkl")
P1_END = pd.Timestamp("2020-12-31")
P2_END = pd.Timestamp("2023-12-31")


def load_panel(cache="broad_nse_10y"):
    obj = pickle.load(open(os.path.join(BASE, "cache", cache + ".pkl"), "rb"))
    return obj["data"] if isinstance(obj, dict) and "data" in obj else obj


def build(horizons=(6, 8, 10), force=False):
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
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        rows.append(d)
    flat = pd.concat(rows, ignore_index=True)
    flat = flat[flat["liq"]].copy()
    for h in horizons:
        flat[f"fwd{h}_dm"] = flat[f"fwd{h}"] - flat.groupby("date")[f"fwd{h}"].transform("mean")
    names = sorted(flat["ticker"].unique())
    rng = np.random.default_rng(23)                       # fresh split seed
    a = set(rng.permutation(names)[: len(names) // 2])
    flat["half"] = np.where(flat["ticker"].isin(a), "A", "B")
    flat["period"] = np.where(flat["date"] <= P1_END, "P1",
                              np.where(flat["date"] <= P2_END, "P2", "P3"))
    pickle.dump(flat, open(CACHE, "wb"))
    return flat


def dayt(sub, col="fwd8_dm"):
    s = sub.dropna(subset=[col])
    if len(s) < 80:
        return (np.nan, np.nan, 0)
    dly = s.groupby("date")[col].mean()
    if len(dly) < 10:
        return (np.nan, np.nan, len(dly))
    return (dly.mean(), dly.mean() / (dly.std(ddof=1) / np.sqrt(len(dly))), len(dly))


CELLS = [(h, p) for h in ("A", "B") for p in ("P1", "P2", "P3")]


def cells(sel, col="fwd8_dm"):
    """Return the 6 (half, period) cell t-stats plus the pooled one."""
    out = {}
    for h, p in CELLS:
        out[f"{h}{p}"] = dayt(sel[(sel.half == h) & (sel.period == p)], col)
    out["ALL"] = dayt(sel, col)
    return out


def fmt_cells(c):
    parts = [f"{k}{c[k][1]:+5.2f}" for k in [f"{h}{p}" for h, p in CELLS]]
    return " ".join(parts) + f"  | ALL {c['ALL'][0]:+.3f}%/t{c['ALL'][1]:+5.2f}"


def score(c):
    """How many of the 6 cells agree with the pooled sign at |t| >= 1.5, and the min |t|."""
    ts = [c[f"{h}{p}"][1] for h, p in CELLS]
    if not all(np.isfinite(t) for t in ts):
        return (-1, 0.0)
    sgn = np.sign(c["ALL"][1])
    agree = sum(1 for t in ts if np.sign(t) == sgn and abs(t) >= 1.5)
    same_sign = sum(1 for t in ts if np.sign(t) == sgn)
    return (agree, same_sign)
