"""Search lab, v2. Fixes the trap that killed strategy 020: a pattern found on one set of names
looked real on a hold-out PERIOD but did not exist on other names.

Protocol:
  SEARCH  = half A of the 484-name NSE panel, dates <= 2025-06-30
  VALID-U = half B of the names (never searched), dates <= 2025-06-30
  VALID-T = both halves, 2025-07-01 .. 2026-08-21 (forward window, never searched)
An idea must show the same sign and comparable strength on SEARCH and VALID-U before it is worth
running through the real engine at all.

Builds a single flat feature frame once and caches it.
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_END = pd.Timestamp("2025-06-30")
FWD_START = pd.Timestamp("2025-07-01")
MIN_TURNOVER = 25e7
FLAT_CACHE = os.path.join(BASE, "cache", "_lab_flat.pkl")

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}


def load_panel(cache="broad_nse_5y"):
    obj = pickle.load(open(os.path.join(BASE, "cache", cache + ".pkl"), "rb"))
    return obj["data"] if isinstance(obj, dict) and "data" in obj else obj


def _market(panel):
    rets = {}
    for t, df in panel.items():
        s = pd.Series(df["close"].pct_change().values, index=df["date"].values)
        rets[t] = s[~s.index.duplicated()]
    return pd.DataFrame(rets).mean(axis=1).sort_index()


def features(d, mkt):
    c, v, h, l, o = d["close"], d["volume"], d["high"], d["low"], d["open"]
    r = c.pct_change()
    d["ret1"] = r * 100
    for k in (2, 3, 5, 10, 20, 60, 120):
        d[f"ret{k}"] = c.pct_change(k) * 100
    d["vol50"] = v.rolling(50).mean()
    d["vol_ratio1"] = v / d["vol50"]
    d["vol_ratio3"] = v.rolling(3).mean() / d["vol50"]
    d["turn20"] = d["turnover"].rolling(20).mean()
    d["turn_ratio20"] = d["turn20"] / d["turnover_60d"]
    sign = np.sign(c.diff().fillna(0))
    d["obv_ch20"] = (sign * v).cumsum().diff(20) / d["vol50"].replace(0, np.nan) / 20
    d["rng_pos"] = (c - l) / (h - l).replace(0, np.nan)
    d["rng_pos5"] = d["rng_pos"].rolling(5).mean()
    d["low20"] = l.rolling(20).min()
    d["high20"] = h.rolling(20).max()
    d["high10"] = h.rolling(10).max()
    d["dist_high10"] = c / d["high10"] - 1
    d["dist_high20"] = c / d["high20"] - 1
    d["dist_high250"] = c / h.rolling(250).max() - 1
    d["atr_pct_rank"] = d["atr_pct"].rolling(250).rank(pct=True)
    d["drop_atr5"] = (c - c.shift(5)) / d["atr"]
    tp = (h + l + c) / 3
    d["dev_avwap"] = (c / ((tp * v).rolling(20).sum() / v.rolling(20).sum()) - 1) * 100
    bm, bs = c.rolling(20).mean(), c.rolling(20).std()
    d["bb_bw"] = 4 * bs / bm
    d["bb_bw_rank"] = d["bb_bw"].rolling(250).rank(pct=True)
    d["bb_pos"] = (c - (bm - 2 * bs)) / (4 * bs).replace(0, np.nan)
    dn = (c.diff() < 0).astype(int)
    d["dn_streak"] = dn * (dn.groupby((dn != dn.shift()).cumsum()).cumcount() + 1)
    d["turnover_z"] = (d["turnover"] - d["turnover"].rolling(60).mean()) / d["turnover"].rolling(60).std()
    d["up_days20"] = (c.diff() > 0).rolling(20).mean()
    d["vol20"] = r.rolling(20).std() * 100
    d["vol60"] = r.rolling(60).std() * 100
    d["vol_ratio_2060"] = d["vol20"] / d["vol60"]
    d["sharpe60"] = d["ret60"] / (d["vol60"] * np.sqrt(60)).replace(0, np.nan)
    d["gap"] = (o / c.shift(1) - 1) * 100
    d["co_ret"] = (c / o - 1) * 100                      # intraday
    d["oc_gap20"] = d["gap"].rolling(20).mean()          # overnight drift
    d["intraday20"] = d["co_ret"].rolling(20).mean()
    d["skew60"] = r.rolling(60).skew()
    d["kurt60"] = r.rolling(60).kurt()
    d["maxret20"] = d["ret1"].rolling(20).max()
    d["ret_ex1_5"] = d["ret5"] - d["ret1"]               # 5d return excluding the last day
    d["ret_ex5_20"] = d["ret20"] - d["ret5"]
    d["ret_ex20_120"] = d["ret120"] - d["ret20"]         # intermediate momentum
    d["close_sma20"] = c / d["sma_20"] - 1
    d["close_sma50"] = c / d["sma_50"] - 1
    d["close_sma200"] = c / d["sma_200"] - 1
    d["sma20_slope"] = d["sma_20"].pct_change(5) * 100
    d["sma50_slope"] = d["sma_50"].pct_change(10) * 100
    d["amihud"] = (r.abs() / d["turnover"].replace(0, np.nan)).rolling(20).mean()
    d["amihud_z"] = (d["amihud"] - d["amihud"].rolling(250).mean()) / d["amihud"].rolling(250).std()
    idx = pd.Index(d["date"].values)
    m1 = mkt.reindex(idx).values * 100
    d["mkt1"] = m1
    d["mkt5"] = pd.Series(m1).rolling(5).sum().values
    d["mkt20"] = pd.Series(m1).rolling(20).sum().values
    d["beta"] = pd.Series(d["ret1"].values).rolling(120).cov(pd.Series(m1)) / pd.Series(m1).rolling(120).var()
    d["resid5"] = d["ret5"] - d["beta"] * d["mkt5"]
    d["resid20"] = d["ret20"] - d["beta"] * d["mkt20"]
    d["corr_mkt"] = pd.Series(d["ret1"].values).rolling(60).corr(pd.Series(m1))
    d["idio_vol"] = d["vol60"] * np.sqrt(np.clip(1 - d["corr_mkt"] ** 2, 0, 1))
    return d


def build_flat(horizons=(6, 8, 10), force=False):
    if os.path.exists(FLAT_CACHE) and not force:
        return pickle.load(open(FLAT_CACHE, "rb"))
    panel = load_panel()
    mkt = _market(panel)
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
    # fixed, reproducible half-split of the NAMES
    names = sorted(flat["ticker"].unique())
    rng = np.random.default_rng(7)
    half = set(rng.permutation(names)[: len(names) // 2])
    flat["half"] = np.where(flat["ticker"].isin(half), "A", "B")
    pickle.dump(flat, open(FLAT_CACHE, "wb"))
    return flat


def dayt(sub, col="fwd8_dm"):
    s = sub.dropna(subset=[col])
    if len(s) < 100:
        return (np.nan, np.nan, 0)
    dly = s.groupby("date")[col].mean()
    if len(dly) < 10:
        return (np.nan, np.nan, len(dly))
    return (dly.mean(), dly.mean() / (dly.std(ddof=1) / np.sqrt(len(dly))), len(dly))


def evaluate(flat, mask_fn, label, col="fwd8_dm", mid_small=True):
    """Report the same statistic on SEARCH (half A, in-sample), VALID-U (half B, in-sample) and
    VALID-T (both halves, forward window). Real effects show up in all three."""
    df = flat[flat["mid_small"]] if mid_small else flat
    try:
        m = mask_fn(df)
    except Exception as e:
        return f"{label:34s} ERROR {e!r}"[:120]
    sel = df[m]
    parts = []
    for name, sub in (("SEARCH", sel[(sel.half == "A") & (sel.date <= IS_END)]),
                      ("VALID-U", sel[(sel.half == "B") & (sel.date <= IS_END)]),
                      ("VALID-T", sel[sel.date >= FWD_START])):
        mm, tt, nn = dayt(sub, col)
        parts.append(f"{name} {mm:+.3f}%/t{tt:+5.2f}/d{nn:4d}" if nn else f"{name} --")
    return f"{label:34s} n={len(sel):6d}  " + " | ".join(parts)


def xrank(df, col, group_extra=None):
    """Cross-sectional daily pct-rank of a column (within the frame given)."""
    return df.groupby("date")[col].rank(pct=True)
