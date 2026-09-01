"""Strategy 034 — Low Idiosyncratic Volatility 52 Week High Volume Thrust in Liquid Mid Small Caps.

Tests whether stocks trading within 5% of their 52-week high that possess low idiosyncratic
volatility (bottom 40% cross-sectionally) and experience an institutional volume surge
(Volume >= 1.8x 20d median) with an upward price thrust (Ret1 >= +1.5% and Close > Open)
exhibit durable swing alpha over a 10-session (2-week) holding horizon.

Tested on 10-year master panel (2016–2026).
Run:  python strategies/034_low_idiosyncratic_volatility_52_week_high_volume_thrust_in_liquid_mid_small_caps.py
"""

import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from backtest_engine import (
    simulate_trades, day_clustered_edge, stable_day_clustered_z,
    edge_vs_control, sharpe, deflated_sharpe, effective_trials,
    round_trip_cost_pct, report
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TURNOVER = 25e7
HORIZON = 10 # 10 trading sessions (2 calendar weeks)
LO, HI = pd.Timestamp("2000-01-01"), pd.Timestamp("2026-08-21")

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}

def load_panel():
    path = os.path.join(BASE, "cache", "_master_flat.pkl")
    if not os.path.exists(path):
        path = os.path.join(BASE, "cache", "_deliv_flat.pkl")
    df = pickle.load(open(path, "rb"))
    
    # Filter liquid mid/small
    mask_liq = (df['turnover_60d'] >= MIN_TURNOVER) & (df['mid_small'] == True)
    d = df[mask_liq].copy().reset_index(drop=True)
    
    # Precompute cross-sectional features
    d['idio_vol_pct'] = d.groupby('date')['idio_vol'].transform(lambda x: x.rank(pct=True))
    d['vol_mom_incumbent'] = d['change_252d'] / d['vol60'].replace(0, np.nan)
    d['incumbent_top_quartile'] = d.groupby('date')['vol_mom_incumbent'].transform(lambda x: x >= x.quantile(0.75))
    
    # Base Signal
    # Near 52w high + Low idio vol + Volume surge + Upward green thrust
    d['green_bar'] = d['close'] > d['open']
    d['sig'] = (
        (d['dist_high250'] >= -0.05) &
        (d['idio_vol_pct'] <= 0.40) &
        (d['vol_ratio1'] >= 1.80) &
        (d['ret1'] >= 1.50) &
        d['green_bar']
    )
    
    panel = {t: grp.sort_values('date').reset_index(drop=True) for t, grp in d.groupby('ticker') if len(grp) >= 300}
    return panel, df

def run_trades_set(sub, horizon=HORIZON, next_open=False, vol_cut=1.8, ret_cut=1.5, idio_cut=0.40):
    strat = []
    stocks = []
    
    for t, d in sub.items():
        sig = (
            (d['dist_high250'] >= -0.05) &
            (d['idio_vol_pct'] <= idio_cut) &
            (d['vol_ratio1'] >= vol_cut) &
            (d['ret1'] >= ret_cut) &
            (d['close'] > d['open'])
        ).fillna(False).values
        
        tr = simulate_trades(d, sig, horizon_days=horizon, charge_costs=True,
                             stop_atr_mult=99.0, target_atr_mult=99.0)
        for item in tr:
            item["ticker"] = t
            if next_open:
                idx = item["entry_idx"]
                if idx + 1 < len(d):
                    nxt_open = d["open"].iat[idx + 1]
                    item["entry_date"] = d["date"].iat[idx + 1]
                    exit_px = d["close"].iat[min(idx + 1 + horizon, len(d) - 1)]
                    gross = (exit_px - nxt_open) / nxt_open * 100
                    item["gross_pct"] = gross
                    item["net_pct"] = gross - item["cost_pct"]
        strat.extend(tr)
        stocks.append((t, d))
        
    def control_factory(seed, mode="random"):
        rng = np.random.default_rng(seed)
        ctrl = []
        for t, d in stocks:
            if mode == "random":
                rnd = (rng.random(len(d)) < 0.05)
            elif mode == "mom_incumbent":
                rnd = d['incumbent_top_quartile'].fillna(False).values
            ct = simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True,
                                 stop_atr_mult=99.0, target_atr_mult=99.0)
            for item in ct:
                item["ticker"] = t
            ctrl.extend(ct)
        return ctrl

    return strat, control_factory

def summarize(label, strat, cf, n_seeds=20, mode="random"):
    if not strat:
        print(f"{label}: NO TRADES", flush=True)
        return None
    c0 = cf(42, mode=mode)
    ev = edge_vs_control([t["net_pct"] for t in strat], [t["net_pct"] for t in c0])
    dc = day_clustered_edge(strat, c0)
    sc = stable_day_clustered_z(strat, lambda s: cf(s, mode=mode), n_seeds=n_seeds)
    print(f"{label:<40} | Tr: {len(strat):5d} | Day: {dc['n_paired_days']:4d} | "
          f"Stable Mean z: {sc['mean_z']:+5.2f} (pass {sc['pass_rate']*100:3.0f}%, min {sc['min_z']:+5.2f}, max {sc['max_z']:+5.2f}) | "
          f"DayEdge: {dc['day_edge']:+6.3f}% | Net/tr: {ev['strategy_avg']:+6.3f}% (ctrl {ev['control_avg']:+6.3f}%)",
          flush=True)
    return {"ev": ev, "dc": dc, "sc": sc}

def run_main():
    print("=" * 80)
    print("STRATEGY 034 — LOW IDIOSYNCRATIC VOLATILITY 52-WEEK HIGH VOLUME THRUST")
    print("Universe: Liquid Mid/Small Caps (ex-Nifty50), >= Rs 25cr turnover floor")
    print("=" * 80)
    
    panel, full_df = load_panel()
    print(f"Loaded {len(panel)} liquid mid/small cap stocks.\n")
    
    tickers = sorted(panel.keys())
    half_a_tickers = set(tickers[::2])
    half_b_tickers = set(tickers[1::2])
    
    first_dates = full_df.groupby('ticker')['date'].min()
    pre_2017_tickers = set(first_dates[first_dates <= pd.Timestamp('2017-01-01')].index)
    
    panel_b = {t: d for t, d in panel.items() if t in half_b_tickers}
    panel_pre = {t: d for t, d in panel.items() if t in pre_2017_tickers}
    
    # 1. Primary Full-Sample Test
    print("--- 1. HEADLINE RESULTS (H=10 Sessions) ---")
    st_pool, cf_pool = run_trades_set(panel)
    summarize("Pooled vs Random Control", st_pool, cf_pool, n_seeds=20, mode="random")
    summarize("Pooled vs Incumbent Momentum (§10)", st_pool, cf_pool, n_seeds=1, mode="mom_incumbent")
    
    # 2. Holdout Half B Subgroup Test (§8)
    print("\n--- 2. HOLDOUT HALF B SUBGROUP TEST (§8) ---")
    st_b, cf_b = run_trades_set(panel_b)
    summarize("Holdout Half B vs Random", st_b, cf_b, n_seeds=20, mode="random")
    summarize("Holdout Half B vs Incumbent", st_b, cf_b, n_seeds=1, mode="mom_incumbent")
    
    # 3. Pre-2017 Survivorship Test
    print("\n--- 3. SURVIVORSHIP TEST (Pre-2017 Listings Only) ---")
    st_pre, cf_pre = run_trades_set(panel_pre)
    summarize("Pre-2017 Listings vs Random", st_pre, cf_pre, n_seeds=20, mode="random")
    summarize("Pre-2017 Listings vs Incumbent", st_pre, cf_pre, n_seeds=1, mode="mom_incumbent")
    
    # 4. Next-Open Execution Check
    print("\n--- 4. EXECUTION TIMING CHECK (Next-Open Entry Fill) ---")
    st_nxt, cf_nxt = run_trades_set(panel, next_open=True)
    summarize("Next-Open Entry vs Random", st_nxt, cf_nxt, n_seeds=20, mode="random")
    summarize("Next-Open Entry vs Incumbent", st_nxt, cf_nxt, n_seeds=1, mode="mom_incumbent")
    
    # 5. Walk-Forward Chronological Splits
    print("\n--- 5. WALK-FORWARD CHRONOLOGICAL FOLDS ---")
    all_dates = sorted({d for t in st_pool for d in [t['entry_date']]})
    fold_size = len(all_dates) // 5
    for fold in range(5):
        f_start = all_dates[fold * fold_size]
        f_end = all_dates[min((fold + 1) * fold_size - 1, len(all_dates) - 1)]
        f_strat = [t for t in st_pool if f_start <= t['entry_date'] <= f_end]
        c0 = cf_pool(42, mode="random")
        f_ctrl = [t for t in c0 if f_start <= t['entry_date'] <= f_end]
        dc = day_clustered_edge(f_strat, f_ctrl)
        net_m = np.mean([t['net_pct'] for t in f_strat]) if f_strat else 0
        z_p = dc['z_paired'] if dc else 0
        de = dc['day_edge'] if dc else 0
        print(f"Fold {fold+1} ({str(f_start)[:10]} to {str(f_end)[:10]}): Tr={len(f_strat):4d}, Net={net_m:+6.3f}%, DayEdge={de:+6.3f}%, z_paired={z_p:+5.2f}")
        
    # 6. Sensitivity Grid (Volume and Return Hurdles)
    print("\n--- 6. PARAMETER SENSITIVITY GRID ---")
    for vc in [1.5, 1.8, 2.2]:
        for rc in [1.0, 1.5, 2.0]:
            st_sens, cf_sens = run_trades_set(panel, vol_cut=vc, ret_cut=rc)
            dc = day_clustered_edge(st_sens, cf_sens(42))
            net_m = np.mean([t['net_pct'] for t in st_sens]) if st_sens else 0
            zp = dc['z_paired'] if dc else 0
            print(f"Vol>{vc:3.1f}x Ret>{rc:3.1f}% | Trades: {len(st_sens):4d} | Net/tr: {net_m:+6.3f}% | DayEdge: {dc['day_edge'] if dc else 0:+6.3f}% | z_paired: {zp:+5.2f}")

if __name__ == "__main__":
    run_main()

