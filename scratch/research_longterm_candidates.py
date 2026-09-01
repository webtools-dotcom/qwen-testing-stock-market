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
HORIZON = 30  # ~1.5 months (30 trading sessions)

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
        
        # Forward returns: 30-session future return
        d["fwd_ret_30"] = d["close"].shift(-HORIZON) / d["close"] - 1.0
        
        # Returns and vol
        r = d["close"].pct_change()
        d["vol60"] = r.rolling(60).std() * 100
        d["vol252"] = r.rolling(252).std() * 100
        
        # 1. 52-week High Nearness (George & Hwang 2004)
        high_252 = d["high"].rolling(252).max()
        d["near_52w_high"] = d["close"] / high_252
        
        # 2. Frog-in-the-pan / Continuous Momentum (Da et al. 2014)
        # Ratio of positive return days to total trading days over past 252 sessions
        pos_days_252 = (r > 0).astype(float).rolling(252).mean()
        neg_days_252 = (r < 0).astype(float).rolling(252).mean()
        # Information discreteness
        ret_252 = d["close"] / d["close"].shift(252) - 1.0
        d["fip_id"] = np.sign(ret_252) * (neg_days_252 - pos_days_252) # lower is smoother positive momentum
        d["fip_pos_pct"] = pos_days_252 # higher = more consistent positive days
        d["t_stat_252"] = (r.rolling(252).mean() / (r.rolling(252).std() + 1e-8)) * np.sqrt(252)
        
        # 3. Intermediate Momentum ex 1 month (126d ex 21d)
        d["mom_126_21"] = d["close"].shift(21) / d["close"].shift(126) - 1.0
        
        # 4. Low Volatility Factor
        d["low_vol_252"] = -d["vol252"] # higher = lower vol
        d["low_vol_60"] = -d["vol60"]
        
        # 5. Trend Alignment / Moving Average Spread
        sma_50 = d["sma_50"]
        sma_200 = d["sma_200"]
        d["trend_spread"] = (d["close"] - sma_50) / sma_50 + (sma_50 - sma_200) / sma_200
        
        # 6. Donchian 100-day High Breakout Distance
        high_100 = d["high"].rolling(100).max()
        d["donchian_100"] = d["close"] / high_100
        
        # 7. Sharpe-like 6-Month Momentum: 126d return / 60d vol
        d["risk_adj_mom_126"] = (d["close"] / d["close"].shift(126) - 1.0) / (d["vol60"] + 1e-4)
        
        # 8. 12-Month Momentum / Vol (Strategy 022/024 signal for comparison)
        d["risk_adj_mom_252"] = d["change_252d"] / (d["vol60"] + 1e-4)

        d["liq"] = (d["turnover_60d"] >= MIN_TURNOVER).fillna(False)
        prepped[t] = d
        
    return prepped

def screen_factors(prepped):
    # Combine into a single long dataframe
    cols = ["date", "ticker", "liq", "mid_small", "fwd_ret_30", 
            "near_52w_high", "fip_pos_pct", "fip_id", "t_stat_252", 
            "mom_126_21", "low_vol_252", "trend_spread", "donchian_100", 
            "risk_adj_mom_126", "risk_adj_mom_252"]
    
    flat = pd.concat([d[cols] for d in prepped.values()], ignore_index=True)
    
    # Filter for liquid mid/small caps
    elig = flat[flat["liq"] & flat["mid_small"] & flat["fwd_ret_30"].notna()].copy()
    
    # Compute day-demeaned forward returns to remove market beta on every day
    elig["mkt_fwd"] = elig.groupby("date")["fwd_ret_30"].transform("mean")
    elig["day_demeaned_fwd"] = elig["fwd_ret_30"] - elig["mkt_fwd"]
    
    # Split into Half A and Half B (fixed seed)
    all_tickers = sorted(elig["ticker"].unique())
    rng = np.random.default_rng(23)
    half_A = set(rng.permutation(all_tickers)[:len(all_tickers)//2])
    
    candidate_features = [
        "near_52w_high", "fip_pos_pct", "t_stat_252", 
        "mom_126_21", "low_vol_252", "trend_spread", "donchian_100", 
        "risk_adj_mom_126", "risk_adj_mom_252"
    ]
    
    print(f"Total eligible name-days: {len(elig):,}")
    print(f"Testing {len(candidate_features)} factors at {HORIZON}-session holding period...\n")
    print(f"{'Factor':<20} | {'D10 Edge':<10} | {'D10 t-stat':<10} | {'D1 Edge':<10} | {'D10-D1 Spread':<12} | {'Half A t':<8} | {'Half B t (Holdout)':<18}")
    print("-" * 105)
    
    for feat in candidate_features:
        # Rank factor cross-sectionally per day into deciles
        valid = elig[elig[feat].notna()].copy()
        valid["decile"] = valid.groupby("date")[feat].transform(
            lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if len(s) >= 10 else np.nan
        )
        valid = valid[valid["decile"].notna()]
        
        # D10 (top decile) and D0 (bottom decile)
        d10 = valid[valid["decile"] == 9]
        d1 = valid[valid["decile"] == 0]
        
        d10_edge = d10["day_demeaned_fwd"].mean() * 100
        d10_se = d10["day_demeaned_fwd"].std() / np.sqrt(len(d10)) * 100
        d10_t = d10_edge / d10_se if d10_se > 0 else 0
        
        d1_edge = d1["day_demeaned_fwd"].mean() * 100
        spread = d10_edge - d1_edge
        
        # Half A vs Half B
        d10_A = d10[d10["ticker"].isin(half_A)]
        d10_B = d10[~d10["ticker"].isin(half_A)]
        
        t_A = (d10_A["day_demeaned_fwd"].mean() / (d10_A["day_demeaned_fwd"].std() / np.sqrt(len(d10_A)))) if len(d10_A) > 10 else 0
        t_B = (d10_B["day_demeaned_fwd"].mean() / (d10_B["day_demeaned_fwd"].std() / np.sqrt(len(d10_B)))) if len(d10_B) > 10 else 0
        
        print(f"{feat:<20} | {d10_edge:>+8.3f}% | {d10_t:>+9.2f} | {d1_edge:>+8.3f}% | {spread:>+10.3f}% | {t_A:>+7.2f} | {t_B:>+10.2f}")

if __name__ == "__main__":
    panel = load_data()
    prepped = compute_features(panel)
    screen_factors(prepped)
