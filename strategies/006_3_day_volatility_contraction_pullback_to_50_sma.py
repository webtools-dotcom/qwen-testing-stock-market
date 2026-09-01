"""Strategy 006 — 3-Day Volatility Contraction Pullback to 50 SMA.

Hypothesis:
In liquid Indian equities (turnover >= ₹25cr/day), when an intermediate relative strength leader
(60-day momentum > 20%, SMA 50 > SMA 200, Close > SMA 200) stages an orderly pullback into its 50-day
SMA institutional support (Low <= 1.01 * SMA 50, Close >= SMA 50) accompanied by 3 consecutive sessions
of contracting daily bar range (Range[t] < Range[t-1] < Range[t-2]), it signals exhaustion of selling
pressure and liquidity absorption at key trend support, setting up a 6–10 day swing rebound.

Run:  python strategies/006_3_day_volatility_contraction_pullback_to_50_sma.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import numpy as np
import pandas as pd
from data_loader import get_panel, CACHE_DIR
from backtest_engine import (
    simulate_trades, day_clustered_edge, edge_vs_control,
    stable_day_clustered_z, walk_forward_splits, deflated_sharpe,
    effective_trials, sharpe, report
)

UNIVERSE = [
    'ABB.NS', 'ABBOTINDIA.NS', 'ABCAPITAL.NS', 'ABFRL.NS', 'ACC.NS', 'ADANIENT.NS', 'ADANIPORTS.NS', 'ADANIPOWER.NS',
    'ALKEM.NS', 'AMBER.NS', 'AMBUJACEM.NS', 'APLAPOLLO.NS', 'APOLLOHOSP.NS', 'APOLLOTYRE.NS', 'ASHOKLEY.NS',
    'ASIANPAINT.NS', 'ASTRAL.NS', 'AUBANK.NS', 'AUROPHARMA.NS', 'AXISBANK.NS', 'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS',
    'BAJFINANCE.NS', 'BALKRISIND.NS', 'BANDHANBNK.NS', 'BANKBARODA.NS', 'BATAINDIA.NS', 'BEL.NS', 'BEML.NS',
    'BERGEPAINT.NS', 'BHARATFORG.NS', 'BHARTIARTL.NS', 'BHEL.NS', 'BIOCON.NS', 'BPCL.NS', 'BRITANNIA.NS',
    'BSE.NS', 'BSOFT.NS', 'CANBK.NS', 'CANFINHOME.NS', 'CDSL.NS', 'CHOLAFIN.NS', 'CIPLA.NS', 'COALINDIA.NS',
    'COFORGE.NS', 'COLPAL.NS', 'CONCOR.NS', 'COROMANDEL.NS', 'CROMPTON.NS', 'CUB.NS', 'CUMMINSIND.NS',
    'CYIENT.NS', 'DABUR.NS', 'DALBHARAT.NS', 'DEEPAKNTR.NS', 'DIVISLAB.NS', 'DIXON.NS', 'DLF.NS',
    'DRREDDY.NS', 'EICHERMOT.NS', 'GRASIM.NS', 'HCLTECH.NS', 'HDFCBANK.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'HINDUNILVR.NS', 'ICICIBANK.NS', 'INDUSINDBK.NS', 'INFY.NS', 'ITC.NS', 'JSWSTEEL.NS', 'KOTAKBANK.NS',
    'LALPATHLAB.NS', 'LT.NS', 'M&M.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'NTPC.NS', 'ONGC.NS', 'POWERGRID.NS',
    'RELIANCE.NS', 'SBILIFE.NS', 'SBIN.NS', 'SHRIRAMFIN.NS', 'SUNPHARMA.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS',
    'TCS.NS', 'TECHM.NS', 'TITAN.NS', 'TRENT.NS', 'ULTRACEMCO.NS', 'WIPRO.NS'
]

NIFTY_50 = {
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'SBIN.NS', 'AXISBANK.NS', 'LT.NS', 'ITC.NS',
    'HINDUNILVR.NS', 'MARUTI.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS',
    'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS', 'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS',
    'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS',
    'DIVISLAB.NS', 'EICHERMOT.NS', 'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS',
    'HEROMOTOCO.NS', 'HINDALCO.NS', 'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS',
    'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS'
}

HORIZON = 7
MIN_TURNOVER = 25e7
MOM_MIN = 20.0
SMA_DIST = 1.01

def add_contraction_features(d):
    d['mom_60'] = d['close'].pct_change(60) * 100
    d['range_pct'] = (d['high'] - d['low']) / d['close'] * 100
    d['range_contract_3d'] = (d['range_pct'] < d['range_pct'].shift(1)) & (d['range_pct'].shift(1) < d['range_pct'].shift(2))
    return d

def signal_mask(d, mom_min=MOM_MIN, sma_dist=SMA_DIST):
    contract = d['range_contract_3d']
    touch_50 = (d['low'] <= d['sma_50'] * sma_dist) & (d['close'] >= d['sma_50'])
    trend = (d['mom_60'] > mom_min) & (d['sma_50'] > d['sma_200']) & (d['close'] > d['sma_200'])
    return (contract & touch_50 & trend).fillna(False).values

def run():
    print(f"Loading 5-year panel for {len(UNIVERSE)} liquid NSE stocks...")
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty_research_150_5y")
    print(f"Loaded {len(panel)} stocks.\n")

    valid_dfs = []
    large_dfs = []
    midsmall_dfs = []

    for ticker, df in panel.items():
        d = df.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'sma_50', 'turnover_60d']).reset_index(drop=True)
        if len(d) >= 300:
            d = add_contraction_features(d)
            valid_dfs.append(d)
            if ticker in NIFTY_50:
                large_dfs.append(d)
            else:
                midsmall_dfs.append(d)

    print(f"Usable universe: {len(valid_dfs)} stocks (Large: {len(large_dfs)}, Mid/Small: {len(midsmall_dfs)})\n")

    # Baseline backtest
    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for d in valid_dfs:
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report(f"Strategy 006: 3-Day Volatility Contraction Pullback to 50 SMA ({HORIZON}d, costs charged)", strat, ctrl, holding_days=HORIZON))

    dc = day_clustered_edge(strat, ctrl)
    print("\n--- DAY-CLUSTERED SINGLE-DRAW HEADLINE ---")
    if dc:
        print(f"  z_paired = {dc['z_paired']:.2f}, paired_days = {dc['n_paired_days']}, day_edge = {dc['day_edge']:+.3f}%")

    # Stable 20-seed control
    def control_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
        return c_trades

    stable = stable_day_clustered_z(strat, control_factory, n_seeds=20)
    print("\n--- STABLE 20-SEED DAY-CLUSTERED CONTROL ---")
    if stable:
        print(f"  mean_z: {stable['mean_z']:.2f} | min_z: {stable['min_z']:.2f} | max_z: {stable['max_z']:.2f} | pass_rate: {stable['pass_rate']*100:.1f}% (n_seeds={stable['n_seeds']})")

    # Walk-forward validation (4 purged and embargoed folds)
    sample_len = len(valid_dfs[0])
    splits = list(walk_forward_splits(sample_len, n_splits=4, horizon_days=HORIZON))
    print(f"\n--- WALK-FORWARD VALIDATION ({len(splits)} purged folds) ---")
    for fold_idx, ((tr0, tr1), (te0, te1)) in enumerate(splits, 1):
        f_rng = np.random.default_rng(42 + fold_idx)
        f_strat, f_ctrl = [], []
        for d in valid_dfs:
            test_df = d.iloc[te0:te1].reset_index(drop=True)
            if len(test_df) < HORIZON + 2:
                continue
            liq = (test_df['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_mask(test_df) & liq
            rnd = (f_rng.random(len(test_df)) < 0.08) & liq
            f_strat += simulate_trades(test_df, sig, horizon_days=HORIZON, charge_costs=True)
            f_ctrl += simulate_trades(test_df, rnd, horizon_days=HORIZON, charge_costs=True)

        f_res = edge_vs_control([t['net_pct'] for t in f_strat], [t['net_pct'] for t in f_ctrl])
        f_dc = day_clustered_edge(f_strat, f_ctrl)
        net_edge = f_res['edge'] if f_res else 0.0
        zp = f_dc['z_paired'] if f_dc else 0.0
        de = f_dc['day_edge'] if f_dc else 0.0
        print(f"  Fold {fold_idx} ({te0}:{te1}): trades={len(f_strat):3d}, net_edge={net_edge:+.2f}%, z_paired={zp:+.2f}, day_edge={de:+.2f}%")

    # Execution Timing Test (Next-Open fill vs Same-Close fill)
    print("\n--- EXECUTION TIMING TEST ---")
    s_open, c_open = [], []
    for d in valid_dfs:
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        d_next = d.copy()
        d_next['close'] = d['open'].shift(-1)
        s_open += simulate_trades(d_next.iloc[:-1], sig[:-1], horizon_days=HORIZON, charge_costs=True)
        c_open += simulate_trades(d_next.iloc[:-1], rnd[:-1], horizon_days=HORIZON, charge_costs=True)
    
    def cf_open(seed):
        r = np.random.default_rng(seed)
        c = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (r.random(len(d)) < 0.08) & liq
            d_next = d.copy()
            d_next['close'] = d['open'].shift(-1)
            c += simulate_trades(d_next.iloc[:-1], rnd[:-1], horizon_days=HORIZON, charge_costs=True)
        return c
    
    st_open = stable_day_clustered_z(s_open, cf_open, n_seeds=20)
    res_open = edge_vs_control([t['net_pct'] for t in s_open], [t['net_pct'] for t in c_open])
    print(f"  Next-Open Fill: trades={len(s_open)}, Net={np.mean([t['net_pct'] for t in s_open]):+.2f}%, Edge={res_open['edge']:+.2f}%, mean_z={st_open['mean_z']:.2f}, pass_rate={st_open['pass_rate']*100:.0f}%")

    # Cap-Tier Breakdown
    print("\n--- CAP-TIER BREAKDOWN (§8 check) ---")
    for group_name, grp_dfs in [("Large Caps (Nifty 50)", large_dfs), ("Mid & Small Caps", midsmall_dfs)]:
        g_strat, g_ctrl = [], []
        for d in grp_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_mask(d) & liq
            rnd = (rng.random(len(d)) < 0.08) & liq
            g_strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
            g_ctrl += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
        
        g_res = edge_vs_control([t['net_pct'] for t in g_strat], [t['net_pct'] for t in g_ctrl])
        g_dc = day_clustered_edge(g_strat, g_ctrl)
        
        def g_cf(seed, grp=grp_dfs):
            r = np.random.default_rng(seed)
            c = []
            for d in grp:
                liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
                rnd = (r.random(len(d)) < 0.08) & liq
                c += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
            return c
        
        g_st = stable_day_clustered_z(g_strat, g_cf, n_seeds=15)
        n_t = len(g_strat)
        net_avg = np.mean([t['net_pct'] for t in g_strat]) if g_strat else 0.0
        edge_g = g_res['edge'] if g_res else 0.0
        zp_g = g_dc['z_paired'] if g_dc else 0.0
        mz_g = g_st['mean_z'] if g_st else 0.0
        pr_g = g_st['pass_rate'] * 100 if g_st else 0.0
        print(f"  {group_name:<25}: Trades={n_t:3d}, Net={net_avg:+.2f}%, Edge={edge_g:+.2f}%, Single z_p={zp_g:+.2f}, Stable mean_z={mz_g:+.2f} (pass {pr_g:.0f}%)")

    # Final verdict guide
    print("\n--- VERDICT SUMMARY ---")
    print("Fold 4 is negative (z_paired -0.88, day_edge -0.81%), and trade count collapsed in recent folds (Fold 3 n=3, Fold 4 n=8).")
    print("Multi-strategy search context: 25+ candidates tested in session.")
    print("Verdict per METHODOLOGY.md: REJECT (fails recent fold and sample size requirements).")


if __name__ == "__main__":
    run()
