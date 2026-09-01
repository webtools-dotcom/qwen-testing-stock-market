"""Strategy 003 — Short-Squeeze Volume Thrust in F&O Stocks.

Hypothesis:
In liquid NSE F&O stocks (turnover >= ₹25cr/day), when a stock that has experienced a sharp 5-day
decline (5-day RoC < -5%) suddenly explodes upward (> +2.5% daily gain) on massive volume
(> 2.0x 20-day median volume) and closes in the top quartile of its daily range (close-low / range > 0.75),
it signals short-covering capitulation and aggressive institutional absorption, initiating a 6-10 day
momentum rebound.

Run:  python strategies/003_short_squeeze_volume_thrust_in_f_o_stocks.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from data_loader import get_panel
from backtest_engine import (
    simulate_trades, day_clustered_edge, edge_vs_control,
    stable_day_clustered_z, walk_forward_splits, report
)

# Liquid NSE F&O Universe
UNIVERSE = [
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'AXISBANK.NS',
    'LT.NS', 'ITC.NS', 'HINDUNILVR.NS', 'MARUTI.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS',
    'SUNPHARMA.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS', 'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS',
    'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS',
    'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'EICHERMOT.NS',
    'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS', 'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS',
    'ABB.NS', 'ABBOTINDIA.NS', 'ABCAPITAL.NS', 'ABFRL.NS', 'ACC.NS', 'ADANIENT.NS', 'ADANIPOWER.NS',
    'ALKEM.NS', 'AMBER.NS', 'AMBUJACEM.NS', 'APLAPOLLO.NS', 'APOLLOTYRE.NS', 'ASHOKLEY.NS', 'ASTRAL.NS',
    'AUBANK.NS', 'AUROPHARMA.NS', 'BALKRISIND.NS', 'BANDHANBNK.NS', 'BANKBARODA.NS', 'BATAINDIA.NS',
    'BEL.NS', 'BEML.NS', 'BERGEPAINT.NS', 'BHARATFORG.NS', 'BHEL.NS', 'BIOCON.NS', 'BSE.NS', 'BSOFT.NS',
    'CANBK.NS', 'CANFINHOME.NS', 'CDSL.NS', 'CHOLAFIN.NS', 'COFORGE.NS', 'COLPAL.NS', 'CONCOR.NS',
    'COROMANDEL.NS', 'CROMPTON.NS', 'CUB.NS', 'CUMMINSIND.NS', 'CYIENT.NS', 'DABUR.NS', 'DALBHARAT.NS',
    'DEEPAKNTR.NS', 'DIXON.NS', 'DLF.NS', 'LALPATHLAB.NS'
]

HORIZON = 7
MIN_TURNOVER = 25e7


def signal_mask(d):
    """Short-squeeze volume thrust after a 5-day drop within a structural trend (Close > SMA 200)."""
    roc_5 = d['close'].pct_change(5) * 100
    daily_ret = d['close'].pct_change() * 100
    vol_med = d['volume'].rolling(20).median()
    vol_ratio = d['volume'] / vol_med
    bar_range = (d['high'] - d['low']).replace(0, np.nan)
    bar_pos = (d['close'] - d['low']) / bar_range
    
    return (
        (roc_5.shift(1) < -5.0) &
        (daily_ret > 2.5) &
        (vol_ratio > 2.0) &
        (bar_pos > 0.75) &
        (d['close'] > d['sma_200'])
    )


def run():
    print(f"Loading {len(UNIVERSE)} F&O liquid stocks (5y)...")
    panel = get_panel(UNIVERSE, period="5y", cache_name="nifty_research_150_5y")
    print(f"Got {len(panel)} usable stocks\n")

    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    valid_dfs = []
    
    for ticker, df in panel.items():
        d = df.dropna(subset=['rsi', 'atr', 'close', 'sma_200']).reset_index(drop=True)
        if len(d) < 300:
            continue
        valid_dfs.append(d)
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_mask(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(report(f"Short-Squeeze Volume Thrust in F&O ({HORIZON}d, costs charged)", strat, ctrl))

    # Stable 20-seed control evaluation
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
        print(f"  mean_z: {stable['mean_z']:.2f} | min_z: {stable['min_z']:.2f} | max_z: {stable['max_z']:.2f} | pass_rate: {stable['pass_rate']*100:.1f}%")
        if stable['mean_z'] >= 2.0 and stable['pass_rate'] >= 0.8:
            print("  -> ADOPT-ELIGIBLE (stable across seeds)")
        else:
            print("  -> REJECT (fails stable control bar; mean_z < 2.0)")

    # Walk-Forward Splits
    if valid_dfs:
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
            d_start = valid_dfs[0]['date'].iat[min(te0, sample_len-1)].strftime('%Y-%m-%d')
            d_end = valid_dfs[0]['date'].iat[min(te1-1, sample_len-1)].strftime('%Y-%m-%d')
            if f_res and f_dc:
                print(f"  Fold {fold_idx} ({d_start} to {d_end}): Trades {f_res['n_strategy']:3d} | "
                      f"Net: {f_res['strategy_avg']:+5.2f}% | Edge: {f_res['edge']:+5.2f}% | "
                      f"z_paired: {f_dc['z_paired']:+5.2f} | DayEdge: {f_dc['day_edge']:+5.2f}%")


if __name__ == "__main__":
    run()
