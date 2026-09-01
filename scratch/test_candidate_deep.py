import sys, os, pickle
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scratch"))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z, 
    walk_forward_splits, round_trip_cost_pct
)

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

MIN_TURNOVER = 25e7
P1_END = pd.Timestamp("2020-12-31")
P2_END = pd.Timestamp("2023-12-31")

def load_data():
    obj = pickle.load(open(os.path.join(BASE, "cache", "master_10y.pkl"), "rb"))
    panel = obj["data"] if isinstance(obj, dict) and "data" in obj else obj
    return panel

def prepare(panel):
    rets = {}
    for t, df in panel.items():
        s = pd.Series(df["close"].pct_change().values, index=df["date"].values)
        rets[t] = s[~s.index.duplicated()]
    mkt = pd.DataFrame(rets).mean(axis=1).sort_index()

    prepped = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        r = d["close"].pct_change()
        d["vol60"] = r.rolling(60).std() * 100
        
        # 1. 3-Month Risk-Adjusted Momentum (63 sessions)
        d["score_mom63"] = (d["close"] / d["close"].shift(63) - 1.0) / (d["vol60"] + 1e-4)
        
        # 2. 6-Month Risk-Adjusted Momentum (126 sessions)
        d["score_mom126"] = (d["close"] / d["close"].shift(126) - 1.0) / (d["vol60"] + 1e-4)
        
        # 3. 12-Month ex-1-Month Risk-Adjusted Momentum (252-21 sessions)
        d["score_mom252_21"] = (d["close"].shift(21) / d["close"].shift(252) - 1.0) / (d["vol60"] + 1e-4)
        
        # 4. 252-day Trend T-Stat (Annualized Sharpe)
        d["score_tstat252"] = (r.rolling(252).mean() / (r.rolling(252).std() + 1e-8)) * np.sqrt(252)

        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        m1 = mkt.reindex(pd.Index(d["date"].values)).values * 100
        d["beta"] = (pd.Series(r.values * 100).rolling(120).cov(pd.Series(m1))
                     / pd.Series(m1).rolling(120).var())
        prepped[t] = d

    flat = pd.concat([d[["date", "ticker", "liq", "mid_small", "atr_pct", "beta",
                         "score_mom63", "score_mom126", "score_mom252_21", "score_tstat252"]]
                      for d in prepped.values()], ignore_index=True)
    elig = flat[flat["liq"] & flat["mid_small"]]
    
    for sc in ["score_mom63", "score_mom126", "score_mom252_21", "score_tstat252"]:
        flat.loc[elig.index, f"rank_{sc}"] = elig.groupby("date")[sc].rank(pct=True)
        
    for c, n in (("atr_pct", "vol_t"), ("beta", "beta_t")):
        flat.loc[elig.index, n] = elig.groupby("date")[c].transform(
            lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) if s.notna().sum() >= 3 else np.nan)
            
    key = flat.set_index(["ticker", "date"])
    for t, d in prepped.items():
        sub = key.loc[t]
        idx = pd.Index(d["date"].values)
        for c in ["rank_score_mom63", "rank_score_mom126", "rank_score_mom252_21", "rank_score_tstat252", "vol_t", "beta_t"]:
            d[c] = sub[c].reindex(idx).values
            
    return prepped

def run_tests_for_factor(prepped, rank_col, factor_name, hold=30):
    print(f"\n================================================================================")
    print(f"EVALUATING FACTOR: {factor_name} (HOLD = {hold} SESSIONS)")
    print(f"================================================================================")
    
    names = sorted(prepped)
    rng = np.random.default_rng(23)
    half_A = set(rng.permutation(names)[: len(names) // 2])
    half_B = set(names) - half_A
    
    def get_trades(sub_panel, top_pct=0.90, next_open=False, matched=False):
        strat, stocks = [], []
        for t, d in sub_panel.items():
            if t in NIFTY_50:
                continue
            r = d[rank_col]
            sig = (r >= top_pct) & d["liq"]
            sig = sig.fillna(False).values
            if next_open:
                sig = np.roll(sig, 1)
                sig[0] = False
            trades = simulate_trades(d, sig, horizon_days=hold, charge_costs=True,
                                     stop_atr_mult=99.0, target_atr_mult=99.0)
            strat += trades
            stocks.append(d)
            
        if matched:
            cells = pd.concat([d.loc[(d[rank_col] >= top_pct) & d["liq"], ["date", "vol_t", "beta_t"]]
                               for d in stocks], ignore_index=True).dropna().drop_duplicates()
            cells["_ok"] = True
            stocks = [d.merge(cells, on=["date", "vol_t", "beta_t"], how="left")
                       .assign(_ok=lambda x: x["_ok"].fillna(False)) for d in stocks]

        def control_factory(seed):
            rng_c = np.random.default_rng(1000 + seed)
            ctrl = []
            for d in stocks:
                liq = d["liq"].values
                if matched:
                    rnd = liq & d["_ok"].values & ~(d[rank_col] >= top_pct) & (rng_c.random(len(d)) < 0.5)
                else:
                    rnd = liq & (rng_c.random(len(d)) < 0.10)
                ctrl += simulate_trades(d, rnd, horizon_days=hold, charge_costs=True,
                                       stop_atr_mult=99.0, target_atr_mult=99.0)
            return ctrl
            
        return strat, control_factory

    def summarize_test(label, strat, cf, seeds=20):
        if len(strat) < 20:
            print(f"  {label:<32s} : n={len(strat)} (too few trades)")
            return None
        st = stable_day_clustered_z(strat, cf, n_seeds=seeds)
        ctrl = cf(0)
        dc = day_clustered_edge(strat, ctrl)
        nets = np.array([t["net_pct"] for t in strat])
        cnets = np.array([t["net_pct"] for t in ctrl])
        print(f"  {label:<32s} : n={len(strat):5d} days={dc['n_paired_days']:4d} | "
              f"mean_z={st['mean_z']:+5.2f} (pass {st['pass_rate']*100:3.0f}%) | "
              f"day_edge={dc['day_edge']:+6.3f}% | net={nets.mean():+6.3f}% (ctrl {cnets.mean():+6.3f}%) | "
              f"win={100*(nets>0).mean():.0f}%")
        return {"stable": st, "dc": dc}

    # 1. Pooled & Holdout Half B
    s_pool, cf_pool = get_trades(prepped)
    summarize_test("1. Pooled Full 10y", s_pool, cf_pool)
    
    sub_B = {t: d for t, d in prepped.items() if t in half_B}
    s_B, cf_B = get_trades(sub_B)
    summarize_test("2. Hold-out Half B (Unseen)", s_B, cf_B)
    
    # 2. Regimes
    p1 = {t: d[d["date"] <= P1_END] for t, d in prepped.items()}
    p2 = {t: d[(d["date"] > P1_END) & (d["date"] <= P2_END)] for t, d in prepped.items()}
    p3 = {t: d[d["date"] > P2_END] for t, d in prepped.items()}
    s_p1, cf_p1 = get_trades(p1); summarize_test("3. Regime P1 (2016-2020)", s_p1, cf_p1)
    s_p2, cf_p2 = get_trades(p2); summarize_test("4. Regime P2 (2021-2023)", s_p2, cf_p2)
    s_p3, cf_p3 = get_trades(p3); summarize_test("5. Regime P3 (2024-2026)", s_p3, cf_p3)
    
    # 3. Survivorship pre-2017
    first = {t: d["date"].min() for t, d in prepped.items()}
    old = {t: d for t, d in prepped.items() if first[t] <= pd.Timestamp("2017-01-01")}
    s_old, cf_old = get_trades(old)
    summarize_test("6. Survivorship: Pre-2017 Only", s_old, cf_old)
    
    # 4. Matched & Next Open
    s_mat, cf_mat = get_trades(prepped, matched=True)
    summarize_test("7. Vol/Beta-MATCHED Control", s_mat, cf_mat)
    
    s_nxt, cf_nxt = get_trades(prepped, next_open=True)
    summarize_test("8. Next-Session Entry", s_nxt, cf_nxt)

def main():
    panel = load_data()
    prepped = prepare(panel)
    
    run_tests_for_factor(prepped, "rank_score_mom63", "3-Month (63d) Risk-Adjusted Momentum", hold=21)
    run_tests_for_factor(prepped, "rank_score_mom63", "3-Month (63d) Risk-Adjusted Momentum", hold=30)
    run_tests_for_factor(prepped, "rank_score_mom126", "6-Month (126d) Risk-Adjusted Momentum", hold=30)
    run_tests_for_factor(prepped, "rank_score_tstat252", "252d Trend T-Stat / Sharpe", hold=30)

if __name__ == "__main__":
    main()
