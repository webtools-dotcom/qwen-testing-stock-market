import os, sys, pickle
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

MIN_TURNOVER = 25e7

def load_data():
    obj = pickle.load(open(os.path.join(BASE, "cache", "master_10y.pkl"), "rb"))
    panel = obj["data"] if isinstance(obj, dict) and "data" in obj else obj
    return panel

def compute_features(panel):
    prepped = {}
    for t, df in panel.items():
        d = df.copy().reset_index(drop=True)
        d["ticker"] = t
        d["mid_small"] = t not in NIFTY_50
        
        # Returns
        r = d["close"].pct_change()
        d["ret_1"] = r
        d["vol60"] = r.rolling(60).std() * 100
        d["vol252"] = r.rolling(252).std() * 100
        
        # 1. George & Hwang 52-week High Nearness
        high_252 = d["high"].rolling(252).max()
        d["near_52w_high"] = d["close"] / high_252
        
        # 2. 52-Week High Nearness in Uptrend (close > sma_200)
        d["near_52w_uptrend"] = np.where(d["close"] > d["sma_200"], d["near_52w_high"], np.nan)
        
        # 3. 252-day t-statistic of daily returns (Sharpe of trend)
        d["t_stat_252"] = (r.rolling(252).mean() / (r.rolling(252).std() + 1e-8)) * np.sqrt(252)
        
        # 4. 6-Month Risk-Adjusted Momentum (126-session)
        ret_126 = d["close"] / d["close"].shift(126) - 1.0
        d["risk_adj_mom_126"] = ret_126 / (d["vol60"] + 1e-4)
        
        # 5. Momentum Acceleration: 6m return minus prior 6m return (ret_126 - ret_252_126)
        ret_252_126 = d["close"].shift(126) / d["close"].shift(252) - 1.0
        d["mom_accel_126"] = ret_126 - ret_252_126
        
        # 6. Volatility Contraction near 52w high: near_52w_high / (vol60 + 1e-4)
        d["vcp_factor"] = d["near_52w_high"] / (d["vol60"] + 1e-4)
        
        # 7. Donchian 252-day Channel Breakout Ratio
        high_126 = d["high"].rolling(126).max()
        d["near_126d_high"] = d["close"] / high_126
        
        # 8. Intermediate 3-Month Momentum (63 sessions)
        ret_63 = d["close"] / d["close"].shift(63) - 1.0
        d["risk_adj_mom_63"] = ret_63 / (d["vol60"] + 1e-4)
        
        # Forward returns at different horizons: 21d, 30d, 42d (1, 1.5, 2 months)
        d["fwd_ret_21"] = d["close"].shift(-21) / d["close"] - 1.0
        d["fwd_ret_30"] = d["close"].shift(-30) / d["close"] - 1.0
        d["fwd_ret_42"] = d["close"].shift(-42) / d["close"] - 1.0
        
        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        prepped[t] = d
        
    return prepped

def analyze(prepped):
    cols = ["date", "ticker", "liq", "mid_small", "fwd_ret_21", "fwd_ret_30", "fwd_ret_42",
            "near_52w_high", "near_52w_uptrend", "t_stat_252", "risk_adj_mom_126", 
            "mom_accel_126", "vcp_factor", "near_126d_high", "risk_adj_mom_63"]
    
    flat = pd.concat([d[cols] for d in prepped.values()], ignore_index=True)
    elig = flat[flat["liq"] & flat["mid_small"]].copy()
    
    # Add ranks for composite features
    elig["rank_52w"] = elig.groupby("date")["near_52w_high"].rank(pct=True)
    elig["rank_mom126"] = elig.groupby("date")["risk_adj_mom_126"].rank(pct=True)
    elig["rank_tstat252"] = elig.groupby("date")["t_stat_252"].rank(pct=True)
    
    # Composite signals
    elig["comp_52w_mom126"] = (elig["rank_52w"] + elig["rank_mom126"]) / 2.0
    elig["comp_52w_tstat"] = (elig["rank_52w"] + elig["rank_tstat252"]) / 2.0
    
    all_tickers = sorted(elig["ticker"].unique())
    rng = np.random.default_rng(23)
    half_A = set(rng.permutation(all_tickers)[:len(all_tickers)//2])
    
    features = [
        "near_52w_high", "near_52w_uptrend", "t_stat_252", "risk_adj_mom_126", 
        "mom_accel_126", "vcp_factor", "near_126d_high", "risk_adj_mom_63",
        "comp_52w_mom126", "comp_52w_tstat"
    ]
    
    for h in [21, 30, 42]:
        fwd_col = f"fwd_ret_{h}"
        sub = elig[elig[fwd_col].notna()].copy()
        sub["mkt_fwd"] = sub.groupby("date")[fwd_col].transform("mean")
        sub["day_demeaned"] = sub[fwd_col] - sub["mkt_fwd"]
        
        print(f"\n==================== HORIZON: {h} SESSIONS (~{h/21:.1f} MONTHS) ====================")
        print(f"{'Factor':<20} | {'D10 Edge':<10} | {'D10 t-stat':<10} | {'D1 Edge':<10} | {'Spread':<10} | {'Half A t':<8} | {'Half B t (Holdout)':<18}")
        print("-" * 105)
        
        for feat in features:
            valid = sub[sub[feat].notna()].copy()
            valid["decile"] = valid.groupby("date")[feat].transform(
                lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if len(s) >= 10 else np.nan
            )
            valid = valid[valid["decile"].notna()]
            d10 = valid[valid["decile"] == 9]
            d1 = valid[valid["decile"] == 0]
            
            d10_edge = d10["day_demeaned"].mean() * 100
            d10_se = d10["day_demeaned"].std() / np.sqrt(len(d10)) * 100
            d10_t = d10_edge / d10_se if d10_se > 0 else 0
            
            d1_edge = d1["day_demeaned"].mean() * 100
            spread = d10_edge - d1_edge
            
            d10_A = d10[d10["ticker"].isin(half_A)]
            d10_B = d10[~d10["ticker"].isin(half_A)]
            t_A = (d10_A["day_demeaned"].mean() / (d10_A["day_demeaned"].std() / np.sqrt(len(d10_A)))) if len(d10_A) > 10 else 0
            t_B = (d10_B["day_demeaned"].mean() / (d10_B["day_demeaned"].std() / np.sqrt(len(d10_B)))) if len(d10_B) > 10 else 0
            
            print(f"{feat:<20} | {d10_edge:>+8.3f}% | {d10_t:>+9.2f} | {d1_edge:>+8.3f}% | {spread:>+8.3f}% | {t_A:>+7.2f} | {t_B:>+10.2f}")

if __name__ == "__main__":
    panel = load_data()
    prepped = compute_features(panel)
    analyze(prepped)
