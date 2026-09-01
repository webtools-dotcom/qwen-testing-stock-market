"""Candidate screen. Honest engine, non-overlap, costs, day-clustered stable z vs random control.

SEARCH is done ONLY on in-sample bars (<= IS_END). Everything after that is held out and never
looked at until a candidate is otherwise finished (METHODOLOGY 9).
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from backtest_engine import simulate_trades, day_clustered_edge, stable_day_clustered_z

IS_END = pd.Timestamp("2025-06-30")     # search window ends here
MIN_TURNOVER = 25e7
HORIZON = 8

NIFTY_50 = set("""RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI TATASTEEL JSWSTEEL
CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM POWERGRID NTPC ONGC
ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV BHARTIARTL BPCL
HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP COALINDIA
ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split())
NIFTY_50 = {f"{t}.NS" for t in NIFTY_50}


def load(cache):
    obj = pickle.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        "cache", cache + ".pkl"), "rb"))
    return obj["data"] if isinstance(obj, dict) and "data" in obj else obj


def market_series(panel):
    """Equal-weight cross-sectional daily return of the panel = market proxy."""
    rets = {}
    for t, df in panel.items():
        s = pd.Series(df["close"].pct_change().values, index=df["date"].values)
        rets[t] = s[~s.index.duplicated()]
    m = pd.DataFrame(rets).mean(axis=1)
    return m.sort_index()


def enrich(panel):
    mkt = market_series(panel)
    mkt5 = mkt.rolling(5).sum()
    mkt10 = mkt.rolling(10).sum()
    out = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        c, v, h, l, o = d["close"], d["volume"], d["high"], d["low"], d["open"]
        d["ret1"] = c.pct_change() * 100
        for k in (3, 5, 10, 20, 60):
            d[f"ret{k}"] = c.pct_change(k) * 100
        d["vol50"] = v.rolling(50).mean()
        d["vol_ratio3"] = v.rolling(3).mean() / d["vol50"]
        d["vol_ratio5"] = v.rolling(5).mean() / d["vol50"]
        d["vol_ratio1"] = v / d["vol50"]
        sign = np.sign(c.diff().fillna(0))
        d["obv"] = (sign * v).cumsum()
        d["obv_ch20"] = d["obv"].diff(20) / d["vol50"].replace(0, np.nan) / 20
        d["rng_pos"] = (c - l) / (h - l).replace(0, np.nan)
        d["low20"] = l.rolling(20).min()
        d["high20"] = h.rolling(20).max()
        d["high10"] = h.rolling(10).max()
        d["dist_high10"] = c / d["high10"] - 1
        d["atr_pct_rank"] = d["atr_pct"].rolling(250).rank(pct=True)
        r = c.pct_change()
        d["semivol_dn"] = r.where(r < 0).rolling(40).std()
        d["semivol_up"] = r.where(r > 0).rolling(40).std()
        d["semi_ratio"] = d["semivol_dn"] / d["semivol_up"]
        d["amihud"] = (r.abs() / d["turnover"].replace(0, np.nan)).rolling(20).mean()
        d["amihud_z"] = (d["amihud"] - d["amihud"].rolling(250).mean()) / d["amihud"].rolling(250).std()
        idx = pd.Index(d["date"].values)
        d["mkt5"] = mkt5.reindex(idx).values * 100
        d["mkt10"] = mkt10.reindex(idx).values * 100
        d["mkt1"] = mkt.reindex(idx).values * 100
        d["beta"] = (pd.Series(d["ret1"].values).rolling(120).cov(pd.Series(d["mkt1"].values)) /
                     pd.Series(d["mkt1"].values).rolling(120).var())
        d["resid5"] = d["ret5"] - d["beta"] * d["mkt5"]
        d["resid10"] = d["ret10"] - d["beta"] * d["mkt10"]
        d["gap"] = (o / c.shift(1) - 1) * 100
        d["drop_atr5"] = (c - c.shift(5)) / d["atr"]
        d["drop_atr10"] = (c - c.shift(10)) / d["atr"]
        tp = (h + l + c) / 3
        d["avwap20"] = (tp * v).rolling(20).sum() / v.rolling(20).sum()
        d["dev_avwap"] = (c / d["avwap20"] - 1) * 100
        bb_m = c.rolling(20).mean(); bb_s = c.rolling(20).std()
        d["bb_bw"] = (4 * bb_s / bb_m)
        d["bb_bw_rank"] = d["bb_bw"].rolling(250).rank(pct=True)
        d["bb_pos"] = (c - (bb_m - 2 * bb_s)) / (4 * bb_s).replace(0, np.nan)
        dn = (c.diff() < 0).astype(int)
        d["dn_streak"] = dn * (dn.groupby((dn != dn.shift()).cumsum()).cumcount() + 1)
        d["rsi_w"] = d["rsi"].rolling(5).mean()
        d["turnover_z"] = (d["turnover"] - d["turnover"].rolling(60).mean()) / d["turnover"].rolling(60).std()
        d["absorb"] = d["turnover_z"] / (d["ret1"].abs() + 0.5)
        d["up_days20"] = (c.diff() > 0).rolling(20).mean()
        d["path_smooth"] = d["ret20"] / (d["ret1"].rolling(20).std() * np.sqrt(20)).replace(0, np.nan)
        d["gap_fill"] = ((d["gap"] < -1) & (c > o)).astype(int)
        d["ticker"] = t
        out[t] = d
    return out


def add_cs_ranks(panel, cols):
    """Cross-sectional pct-rank of `cols` per date, added as <col>_csr."""
    frames = [d[["date", "ticker"] + cols] for d in panel.values()]
    allf = pd.concat(frames, ignore_index=True)
    for cname in cols:
        allf[cname + "_csr"] = allf.groupby("date")[cname].rank(pct=True)
    key = allf.set_index(["ticker", "date"])
    for t, d in panel.items():
        sub = key.loc[t]
        for cname in cols:
            d[cname + "_csr"] = sub[cname + "_csr"].reindex(pd.Index(d["date"].values)).values
    return panel


def screen(panel, sig_fn, horizon=HORIZON, seeds=8, is_only=True, subset=None,
           start=None, end=None, exit_rsi=None):
    """Run one candidate. Returns dict of stats."""
    strat = []
    per_stock = []          # (df_len, liq_mask, d) kept for control factory
    for t, d in panel.items():
        if subset is not None and not subset(t):
            continue
        dd = d
        lo = start if start is not None else pd.Timestamp("1990-01-01")
        hi = end if end is not None else (IS_END if is_only else pd.Timestamp("2099-01-01"))
        dd = dd[(dd["date"] >= lo) & (dd["date"] <= hi)].reset_index(drop=True)
        dd = dd.dropna(subset=["close", "atr"]).reset_index(drop=True)
        if len(dd) < 260:
            continue
        liq = (dd["turnover_60d"] >= MIN_TURNOVER).fillna(False).values
        try:
            sig = np.asarray(sig_fn(dd), dtype=bool) & liq
        except Exception as e:
            return {"error": repr(e)}
        strat += simulate_trades(dd, sig, horizon_days=horizon, charge_costs=True, exit_rsi=exit_rsi)
        per_stock.append((dd, liq))
    if len(strat) < 20:
        return {"n": len(strat), "mean_z": float("nan"), "note": "too few trades"}

    def control_factory(seed):
        rng = np.random.default_rng(1000 + seed)
        ctrl = []
        for dd, liq in per_stock:
            rnd = (rng.random(len(dd)) < 0.10) & liq
            ctrl += simulate_trades(dd, rnd, horizon_days=horizon, charge_costs=True, exit_rsi=exit_rsi)
        return ctrl

    st = stable_day_clustered_z(strat, control_factory, n_seeds=seeds)
    dc = day_clustered_edge(strat, control_factory(0))
    nets = np.array([t["net_pct"] for t in strat])
    return {"n": len(strat), "mean_z": st["mean_z"], "pass": st["pass_rate"],
            "min_z": st["min_z"], "max_z": st["max_z"],
            "day_edge": dc["day_edge"], "n_days": dc["n_paired_days"],
            "net_avg": float(nets.mean()), "win": float((nets > 0).mean() * 100),
            "trades": strat, "control_factory": control_factory}


def fmt(name, r):
    if "error" in r:
        return f"{name:38s} ERROR {r['error'][:60]}"
    if not np.isfinite(r.get("mean_z", float("nan"))):
        return f"{name:38s} n={r['n']:5d}  {r.get('note','')}"
    return (f"{name:38s} n={r['n']:5d} days={r['n_days']:4d} mean_z={r['mean_z']:+5.2f} "
            f"pass={r['pass']*100:3.0f}% dayedge={r['day_edge']:+.3f}% net={r['net_avg']:+.3f}% "
            f"win={r['win']:.0f}%")
