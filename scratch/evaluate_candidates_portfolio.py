import sys, os, pickle
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scratch"))

import numpy as np
import pandas as pd
from backtest_engine import round_trip_cost_pct, stable_day_clustered_z, day_clustered_edge, simulate_trades

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

MIN_TURNOVER = 25e7
HOLD = 30 # 30 sessions (~1.5 months)
K = 20    # 20 concurrent positions

def load_data():
    obj = pickle.load(open(os.path.join(BASE, "cache", "master_10y.pkl"), "rb"))
    panel = obj["data"] if isinstance(obj, dict) and "data" in obj else obj
    return panel

def compute_all_factors(panel):
    prepped = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        r = d["close"].pct_change()
        d["vol60"] = r.rolling(60).std() * 100
        
        # 1. 52w high nearness (George & Hwang 2004)
        high_252 = d["high"].rolling(252).max()
        d["near_52w"] = d["close"] / high_252
        
        # 2. 252d Trend t-stat (Sharpe of trend)
        d["tstat_252"] = (r.rolling(252).mean() / (r.rolling(252).std() + 1e-8)) * np.sqrt(252)
        
        # 3. 3-Month risk-adj momentum (63 sessions)
        ret_63 = d["close"] / d["close"].shift(63) - 1.0
        d["mom_63_adj"] = ret_63 / (d["vol60"] + 1e-4)
        
        # 4. 6-Month risk-adj momentum (126 sessions)
        ret_126 = d["close"] / d["close"].shift(126) - 1.0
        d["mom_126_adj"] = ret_126 / (d["vol60"] + 1e-4)

        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        prepped[t] = d
        
    flat = pd.concat([d[["date", "ticker", "liq", "mid_small", "near_52w", "tstat_252", "mom_63_adj", "mom_126_adj"]]
                      for d in prepped.values()], ignore_index=True)
    elig = flat[flat["liq"] & flat["mid_small"]]
    
    # Rank factors
    for feat in ["near_52w", "tstat_252", "mom_63_adj", "mom_126_adj"]:
        flat.loc[elig.index, f"rank_{feat}"] = elig.groupby("date")[feat].rank(pct=True)
        
    flat.loc[elig.index, "rank_comp_52w_tstat"] = (flat.loc[elig.index, "rank_near_52w"] + flat.loc[elig.index, "rank_tstat_252"]) / 2.0
    
    key = flat.set_index(["ticker", "date"])
    for t, d in prepped.items():
        sub = key.loc[t]
        idx = pd.Index(d["date"].values)
        for c in ["rank_near_52w", "rank_tstat_252", "rank_mom_63_adj", "rank_mom_126_adj", "rank_comp_52w_tstat"]:
            d[c] = sub[c].reindex(idx).values
            
    return prepped

def run_portfolio(df, rank_col, mode="strategy", k=K, hold=HOLD, seed=0, cost_mult=1.0):
    df = df[df["liq"]].copy()
    dates = np.sort(df["date"].unique())
    px = df.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    rk = df.pivot_table(index="date", columns="ticker", values=rank_col, aggfunc="last")
    to = df.pivot_table(index="date", columns="ticker", values="turnover_60d", aggfunc="last")
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
    open_pos = {} # ticker -> (days_left, weight_value)
    for i, dt in enumerate(dates):
        if open_pos:
            r = ret.loc[dt]
            for t in list(open_pos):
                d_left, val = open_pos[t]
                rr = r.get(t, np.nan)
                val = val * (1 + (0.0 if not np.isfinite(rr) else rr))
                d_left -= 1
                if d_left <= 0:
                    equity += val
                    del open_pos[t]
                else:
                    open_pos[t] = (d_left, val)
        slots = k - len(open_pos)
        if slots > 0 and i < len(dates) - hold - 1:
            row = rk.loc[dt]
            if mode == "strategy":
                cand = row[(row >= 0.90)].sort_values(ascending=False).index.tolist()
            else:
                cand = row[row.notna()].index.tolist()
                rng.shuffle(cand)
            cand = [t for t in cand if t not in open_pos and np.isfinite(px.loc[dt].get(t, np.nan))]
            take = cand[:slots]
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
    print(f"  {name:36s} CAGR {cagr*100:+6.2f}%  maxDD {dd*100:6.1f}%  Sharpe {sh:5.2f}  final {eq.iloc[-1]:.2f}x")
    return {"cagr": cagr, "dd": dd, "sharpe": sh, "eq": eq}

def main():
    panel = compute_all_factors(load_data())
    keep = ["date", "ticker", "close", "liq", "turnover_60d", 
            "rank_near_52w", "rank_tstat_252", "rank_mom_63_adj", "rank_mom_126_adj", "rank_comp_52w_tstat"]
    df = pd.concat([d[keep] for d in panel.values() if d["ticker"].iloc[0] not in NIFTY_50], ignore_index=True)
    df = df.sort_values(["date", "ticker"])
    
    print("=== BENCHMARK (Buy & Hold Universe) ===")
    bench = run_portfolio(df, "rank_near_52w", mode="benchmark")
    stats(bench, "Equal-weight Liquid Mid/Small")
    
    candidates = [
        ("Near 52W High (George-Hwang)", "rank_near_52w"),
        ("252d Trend T-Stat / Sharpe", "rank_tstat_252"),
        ("3-Month Risk-Adj Momentum (63d)", "rank_mom_63_adj"),
        ("6-Month Risk-Adj Momentum (126d)", "rank_mom_126_adj"),
        ("Composite (52w High + T-Stat)", "rank_comp_52w_tstat"),
    ]
    
    for h in [21, 30, 42]:
        print(f"\n=== CANDIDATE PORTFOLIO SIMULATION (HOLD = {h} SESSIONS, K={K}) ===")
        for label, col in candidates:
            eq = run_portfolio(df, col, mode="strategy", hold=h)
            stats(eq, f"{label} (h={h})")

if __name__ == "__main__":
    main()
