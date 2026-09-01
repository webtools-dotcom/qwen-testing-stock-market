"""Macro-shock lead-lag diagnostic.

Hypothesis: macro news (USDINR, crude, gold, copper, US overnight, VIX) is priced instantly in
large caps but diffuses into liquid mid/smalls over days. On day t, score each stock by
    macro_score = sum_f  beta(stock, f) * recent_move(f)
using ONLY factor moves through t-1 (so US closes, which land after the NSE close, are at least a
full session stale - no look-ahead), and buy the top decile.

Look-ahead discipline: every factor return is lagged one session before it enters the score.
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TURNOVER = 25e7
NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

FACTORS = ["usdinr", "brent", "gold", "copper", "spx", "ndx", "dxy", "vix"]


def load_panel(cache):
    obj = pickle.load(open(os.path.join(BASE, "cache", cache + ".pkl"), "rb"))
    return obj["data"] if isinstance(obj, dict) and "data" in obj else obj


def macro_frame():
    mac = pickle.load(open(os.path.join(BASE, "cache", "macro.pkl"), "rb"))
    df = pd.DataFrame({k: v for k, v in mac.items() if k in FACTORS}).sort_index()
    df = df.ffill()
    rets = df.pct_change() * 100
    return rets


def build(cache="broad_nse_10y", horizons=(6, 8, 10), beta_win=120, move_win=3, force=False):
    out_path = os.path.join(BASE, "cache", f"_macro_flat_{cache}.pkl")
    if os.path.exists(out_path) and not force:
        return pickle.load(open(out_path, "rb"))

    panel = load_panel(cache)
    fr = macro_frame()
    # LAG every factor return by one session before it can be used
    fr_lag = fr.shift(1)
    move = fr_lag.rolling(move_win).sum()          # recent macro move, all through t-1

    rows = []
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        idx = pd.Index(d["date"].values)
        r = pd.Series(d["close"].pct_change().values * 100)
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        score = np.zeros(len(d))
        n_ok = np.zeros(len(d))
        for f in FACTORS:
            fret = pd.Series(fr_lag[f].reindex(idx).values)
            fmove = pd.Series(move[f].reindex(idx).values)
            var = fret.rolling(beta_win).var()
            beta = r.rolling(beta_win).cov(fret) / var.replace(0, np.nan)
            d[f"beta_{f}"] = beta.values
            d[f"mv_{f}"] = fmove.values
            contrib = (beta * fmove).values
            ok = np.isfinite(contrib)
            score = np.where(ok, score + np.nan_to_num(contrib), score)
            n_ok += ok
        d["macro_score"] = np.where(n_ok > 0, score, np.nan)
        for h in horizons:
            d[f"fwd{h}"] = (d["close"].shift(-h) / d["close"] - 1) * 100
        d["ret5"] = d["close"].pct_change(5) * 100
        d["ret20"] = d["close"].pct_change(20) * 100
        rows.append(d)

    flat = pd.concat(rows, ignore_index=True)
    flat = flat[flat["liq"]].copy()
    for h in horizons:
        flat[f"fwd{h}_dm"] = flat[f"fwd{h}"] - flat.groupby("date")[f"fwd{h}"].transform("mean")
    names = sorted(flat["ticker"].unique())
    rng = np.random.default_rng(11)                 # NEW split seed - unrelated to the 020/021 one
    half = set(rng.permutation(names)[: len(names) // 2])
    flat["half"] = np.where(flat["ticker"].isin(half), "A", "B")
    pickle.dump(flat, open(out_path, "wb"))
    return flat


def dayt(sub, col="fwd8_dm"):
    s = sub.dropna(subset=[col])
    if len(s) < 100:
        return (np.nan, np.nan, 0)
    dly = s.groupby("date")[col].mean()
    if len(dly) < 10:
        return (np.nan, np.nan, len(dly))
    return (dly.mean(), dly.mean() / (dly.std(ddof=1) / np.sqrt(len(dly))), len(dly))
