"""Strategy 005 — Bullish Hammer Pin-Bar Absorption in Structural Uptrend.

Hypothesis:
In liquid Indian equities (turnover >= ₹25cr/day), when a stock in a structural intermediate uptrend
(Close > SMA 200 and SMA 50 > SMA 200) suffers an intraday selloff that is aggressively rejected
and absorbed by institutional dip-buyers—forming a Bullish Hammer / Pin Bar candlestick with a long
lower shadow (lower wick >= 65% of total bar range, upper wick <= 15%, Close > Open) on above-average
volume (> 1.2x 20-day median)—the liquidity exhaustion of panic sellers and aggressive institutional
support creates a positive mean-reversion swing rebound over the subsequent 6–10 trading days.

Run:  python strategies/005_bullish_hammer_pin_bar_absorption_in_uptrend.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import numpy as np
import pandas as pd
from data_loader import get_panel
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
MIN_LOWER_WICK = 0.65
MAX_UPPER_WICK = 0.15
VOL_MULT = 1.20


def add_hammer_features(d):
    """Add candle shape features."""
    d['bar_range'] = (d['high'] - d['low']).replace(0, np.nan)
    d['lower_wick'] = (d[['open', 'close']].min(axis=1) - d['low']) / d['bar_range']
    d['upper_wick'] = (d['high'] - d[['open', 'close']].max(axis=1)) / d['bar_range']
    d['vol_med_20'] = d['volume'].rolling(20).median()
    return d


def signal_mask(d, min_wick=MIN_LOWER_WICK, max_upper=MAX_UPPER_WICK, vol_mult=VOL_MULT):
    """Bullish Hammer candle in structural 50/200 SMA uptrend with volume confirmation."""
    hammer = (d['lower_wick'] >= min_wick) & (d['upper_wick'] <= max_upper) & (d['close'] > d['open'])
    vol_confirm = d['volume'] > vol_mult * d['vol_med_20']
    uptrend = (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200'])
    return (hammer & vol_confirm & uptrend).fillna(False).values


def run():
    print(f"Loading 5-year panel for {len(UNIVERSE)} liquid NSE stocks...")
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty_research_150_5y")
    print(f"Loaded {len(panel)} stocks.\n")

    valid_dfs = []
    large_dfs = []
    midsmall_dfs = []

    for ticker, df in panel.items():
        d = df.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'sma_50', 'sma_20', 'turnover_60d']).reset_index(drop=True)
        if len(d) >= 300:
            d = add_hammer_features(d)
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

    print(report(f"Strategy 005: Bullish Hammer Absorption ({HORIZON}d hold, costs charged)", strat, ctrl, holding_days=HORIZON))

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

    # Parameter Ladder Sweep & Deflated Sharpe
    print("\n--- PARAMETER LADDER (Wick Depth Gradient) ---")
    wicks = [0.55, 0.60, 0.62, 0.64, 0.65, 0.66, 0.68, 0.70]
    all_srs = []
    trial_rets = []
    print(f"{'Min Wick':<10} {'Trades':<8} {'Net Avg%':<10} {'z_naive':<10} {'z_paired':<10} {'mean_z':<10} {'pass%':<8}")
    for w in wicks:
        s_tr = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_mask(d, min_wick=w) & liq
            s_tr += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        
        s_rets = [t['net_pct'] for t in s_tr]
        trial_rets.append(s_rets)
        sr = sharpe(s_rets, holding_days=HORIZON)
        all_srs.append(sr)
        
        res_w = edge_vs_control(s_rets, [t['net_pct'] for t in ctrl])
        dc_w = day_clustered_edge(s_tr, ctrl)
        
        def cf_w(seed, w=w):
            r = np.random.default_rng(seed)
            c = []
            for d in valid_dfs:
                liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
                rnd = (r.random(len(d)) < 0.08) & liq
                c += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
            return c
        
        st_w = stable_day_clustered_z(s_tr, cf_w, n_seeds=10)
        n_t = len(s_tr)
        net_avg = np.mean(s_rets) if s_rets else 0.0
        z_n = res_w['z'] if res_w else 0.0
        z_p = dc_w['z_paired'] if dc_w else 0.0
        m_z = st_w['mean_z'] if st_w else 0.0
        p_r = st_w['pass_rate'] * 100 if st_w else 0.0
        print(f"{w:<10.2f} {n_t:<8d} {net_avg:<+10.2f} {z_n:<10.2f} {z_p:<10.2f} {m_z:<10.2f} {p_r:<8.0f}")

    eff = effective_trials(trial_rets)
    dsr = deflated_sharpe(max(all_srs), all_srs, n_obs=len(strat))
    print(f"\nEffective trials: {eff:.2f} (from {len(all_srs)} grid points)")
    if dsr:
        print(f"Deflated Sharpe: DSR = {dsr['dsr']:.4f} (Observed SR: {dsr['observed_sr']:.2f}, Noise ceiling: {dsr['noise_ceiling_sr']:.2f})")

    # Cap-Tier Breakdown
    print("\n--- CAP-TIER BREAKDOWN ---")
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

    # Final verdict
    print("\n--- VERDICT ASSESSMENT ---")
    if stable and stable['mean_z'] >= 2.0 and stable['pass_rate'] >= 0.8:
        print("  -> Stable mean_z >= 2.0 and pass_rate >= 80%: Meets pooled bar.")
    else:
        print("  -> Does not meet full ADOPT criteria.")


if __name__ == "__main__":
    run()
