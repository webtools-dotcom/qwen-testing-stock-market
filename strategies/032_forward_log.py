"""Strategy 032 Forward Log Harness.

Tracks live/forward daily picks for Strategy 032 (252-day Sortino Downside-Risk Momentum)
in liquid Mid/Small caps (>= Rs 25 cr/day turnover, ex-Nifty50) at a 21-session holding horizon.
Records picks to strategies/032_forward_log.csv, monitors open positions, and scores
completed trades against the Incumbent Momentum basket (§10).

Can be re-run daily or weekly as new daily bars arrive.
Run: python strategies/032_forward_log.py
"""

import sys, os, pickle
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

MIN_TURNOVER = 25e7
HORIZON = 21
COST_PCT = 0.50 # round-trip cost %
CSV_PATH = os.path.join(BASE, "strategies", "032_forward_log.csv")

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

def load_data():
    path = os.path.join(BASE, "cache", "_explore_flat.pkl")
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    path2 = os.path.join(BASE, "cache", "master_10y.pkl")
    if os.path.exists(path2):
        obj = pickle.load(open(path2, "rb"))
        return obj["data"] if isinstance(obj, dict) and "data" in obj else obj
    raise FileNotFoundError("Master panel cache not found.")

def update_forward_log(start_date="2026-07-01"):
    panel = load_data()
    all_dates = sorted({dt for d in panel.values() for dt in d["date"]})
    date_series = pd.Series(all_dates)
    date_to_idx = {dt: i for i, dt in enumerate(all_dates)}
    
    start_dt = pd.Timestamp(start_date)
    sim_dates = [dt for dt in all_dates if dt >= start_dt]
    
    # Load existing CSV if available
    if os.path.exists(CSV_PATH):
        try:
            df_log = pd.read_csv(CSV_PATH)
            df_log["signal_date"] = pd.to_datetime(df_log["signal_date"])
        except Exception:
            df_log = pd.DataFrame()
    else:
        df_log = pd.DataFrame()
        
    records = []
    seen_keys = set()
    if not df_log.empty and "signal_date" in df_log.columns and "ticker" in df_log.columns:
        for _, row in df_log.iterrows():
            seen_keys.add((row["signal_date"], row["ticker"]))
            records.append(row.to_dict())

    new_picks = 0
    # For each date from start_date to latest date
    for dt in sim_dates:
        d_i = date_to_idx[dt]
        
        # Cross-sectional pool of liquid mid-smalls on day dt
        pool_sortino = []
        pool_mom = []
        
        for t, d in panel.items():
            if t in NIFTY_50:
                continue
            match = d[d["date"] == dt]
            if match.empty:
                continue
            idx_in_stock = match.index[0]
            if idx_in_stock < 252:
                continue
                
            liq = match["turnover_60d"].values[0] >= MIN_TURNOVER
            if not liq:
                continue
                
            px = match["close"].values[0]
            if not np.isfinite(px) or px <= 0:
                continue
                
            sortino_sc = match["sortino252"].values[0] if "sortino252" in match.columns else np.nan
            mom_sc = match["mom_incumbent"].values[0] if "mom_incumbent" in match.columns else np.nan
            
            if np.isfinite(sortino_sc):
                pool_sortino.append((sortino_sc, t, px, idx_in_stock, d))
            if np.isfinite(mom_sc):
                pool_mom.append((mom_sc, t, px, idx_in_stock, d))
                
        if not pool_sortino or not pool_mom:
            continue
            
        pool_sortino.sort(key=lambda x: x[0], reverse=True)
        pool_mom.sort(key=lambda x: x[0], reverse=True)
        
        n_top10 = max(1, int(np.ceil(len(pool_sortino) * 0.10)))
        top_sortino = pool_sortino[:n_top10]
        
        n_top25 = max(1, int(np.ceil(len(pool_mom) * 0.25)))
        top_mom = pool_mom[:n_top25]
        
        # Calculate incumbent basket average return over 21 days for this entry day
        incumbent_net_rets = []
        for _, t_m, px_m, idx_m, df_m in top_mom:
            if idx_m + HORIZON < len(df_m):
                exit_px_m = df_m["close"].iat[idx_m + HORIZON]
                gross_m = (exit_px_m - px_m) / px_m * 100
                incumbent_net_rets.append(gross_m - COST_PCT)
        inc_day_avg = float(np.mean(incumbent_net_rets)) if incumbent_net_rets else np.nan
        
        # Log top Sortino picks
        for sc, ticker, entry_px, idx_s, df_s in top_sortino:
            key = (dt, ticker)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            new_picks += 1
            
            # Check if 21-session hold has completed
            if idx_s + HORIZON < len(df_s):
                exit_dt = df_s["date"].iat[idx_s + HORIZON]
                exit_px = df_s["close"].iat[idx_s + HORIZON]
                gross_ret = (exit_px - entry_px) / entry_px * 100
                net_ret = gross_ret - COST_PCT
                excess = net_ret - inc_day_avg if np.isfinite(inc_day_avg) else np.nan
                status = "COMPLETED"
            else:
                exit_dt = pd.NaT
                exit_px = np.nan
                gross_ret = np.nan
                net_ret = np.nan
                excess = np.nan
                status = "OPEN"
                
            records.append({
                "signal_date": dt.strftime("%Y-%m-%d"),
                "ticker": ticker,
                "entry_close": round(float(entry_px), 2),
                "sortino_score": round(float(sc), 4),
                "status": status,
                "exit_date": exit_dt.strftime("%Y-%m-%d") if pd.notna(exit_dt) else "",
                "exit_close": round(float(exit_px), 2) if np.isfinite(exit_px) else "",
                "gross_ret_pct": round(float(gross_ret), 3) if np.isfinite(gross_ret) else "",
                "net_ret_pct": round(float(net_ret), 3) if np.isfinite(net_ret) else "",
                "incumbent_day_avg_net": round(float(inc_day_avg), 3) if np.isfinite(inc_day_avg) else "",
                "excess_over_incumbent": round(float(excess), 3) if np.isfinite(excess) else ""
            })
            
    out_df = pd.DataFrame(records)
    out_df.sort_values(by=["signal_date", "ticker"], inplace=True)
    out_df.to_csv(CSV_PATH, index=False)
    
    # Compute current status
    completed = out_df[out_df["status"] == "COMPLETED"].copy()
    open_pos = out_df[out_df["status"] == "OPEN"].copy()
    
    print(f"=========================================================================")
    print(f" STRATEGY 032 LIVE FORWARD LOG STATUS                                    ")
    print(f" Log File: {CSV_PATH}                                                    ")
    print(f" Total Forward Picks Recorded: {len(out_df):d} (New this run: {new_picks:d})")
    print(f" Completed 21-Session Trades  : {len(completed):d}                       ")
    print(f" Active Open Positions        : {len(open_pos):d}                        ")
    print(f"=========================================================================\n")
    
    if completed.empty:
        print("Status: INSUFFICIENT DATA YET — 0 completed trades.")
        return
        
    completed["net_ret_pct"] = pd.to_numeric(completed["net_ret_pct"], errors="coerce")
    completed["excess_over_incumbent"] = pd.to_numeric(completed["excess_over_incumbent"], errors="coerce")
    
    day_paired = completed.dropna(subset=["excess_over_incumbent"]).groupby("signal_date")["excess_over_incumbent"].mean()
    n_days = len(day_paired)
    
    print(f"Completed Paired Days: {n_days:d} (Minimum required to evaluate: 15 days)")
    
    if n_days < 15:
        print(f"Running Mean Day Edge vs Incumbent: {day_paired.mean():+.3f}%")
        print(f"Running z_paired vs Incumbent     : {day_paired.mean() / (day_paired.std(ddof=1) / np.sqrt(n_days)):+.2f}" if n_days > 2 and day_paired.std(ddof=1) > 0 else "")
        print("\n>>> STATUS: INSUFFICIENT DATA YET. Out-of-sample forward test requires at least 15 completed paired days.")
    else:
        z_p = day_paired.mean() / (day_paired.std(ddof=1) / np.sqrt(n_days))
        print(f"Running Mean Day Edge vs Incumbent: {day_paired.mean():+.3f}%")
        print(f"Running z_paired vs Incumbent     : {z_p:+.2f}")
        verdict = "PASS-eligible" if z_p >= 2.0 and day_paired.mean() > 0 else "FAIL"
        print(f"\n>>> CURRENT FORWARD VERDICT: {verdict} (z_paired = {z_p:+.2f})")

if __name__ == "__main__":
    update_forward_log(start_date="2026-07-01")
