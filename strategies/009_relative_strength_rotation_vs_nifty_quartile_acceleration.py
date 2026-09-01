"""Strategy 009 - Relative Strength Rotation vs Nifty (Quartile Acceleration).

Hypothesis:
Stocks that rapidly transition from bottom-quartile relative performance (vs Nifty 50 over 20
days) to top-quartile relative performance are catching the inflection point of institutional
sector/thematic rotation. Indian markets exhibit persistent 2-6 week sectoral rotation waves.
By measuring performance *relative* to the index, the signal is partially immunized against
market-beta day-clustering.

Run:  python strategies/009_relative_strength_rotation_vs_nifty_quartile_acceleration.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
import numpy as np
import pandas as pd
from data_loader import CACHE_DIR, get_panel
from backtest_engine import (
    simulate_trades, day_clustered_edge, edge_vs_control,
    stable_day_clustered_z, walk_forward_splits, deflated_sharpe,
    effective_trials, sharpe, report
)

LARGE_CAPS = {
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'AXISBANK.NS',
    'LT.NS', 'ITC.NS', 'HINDUNILVR.NS', 'MARUTI.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS',
    'SUNPHARMA.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS', 'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS',
    'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS',
    'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'EICHERMOT.NS',
    'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS', 'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS'
}

HORIZON = 8
MIN_TURNOVER = 25e7
RS_LOOKBACK = 20
RECENT_LAGGARD_WINDOW = 15
TOP_QUARTILE_PCT = 75
BOTTOM_QUARTILE_PCT = 25
NIFTY_TICKER = "^NSEI"


def build_rs_matrix(valid_dfs, nifty_df):
    """Build a (dates x stocks) DataFrame of relative-strength values, VECTORIZED.

    RS_20d[stock, date] = stock_20d_return - nifty_20d_return
    Then cross-sectionally rank into percentiles each day.
    Returns: rs_pctrank DataFrame (dates x stock_idx), values 0-100.
    """
    # Nifty 20-day returns indexed by date
    nifty = nifty_df.set_index('date')['close'].sort_index()
    nifty_ret = nifty.pct_change(RS_LOOKBACK) * 100

    # Build a wide DataFrame: each column = one stock's 20d return
    stock_rets = {}
    for idx, d in enumerate(valid_dfs):
        s = d.set_index('date')['close'].sort_index()
        stock_rets[idx] = s.pct_change(RS_LOOKBACK) * 100

    stock_ret_df = pd.DataFrame(stock_rets)  # index = date, columns = stock_idx
    # Align with nifty
    common_dates = stock_ret_df.index.intersection(nifty_ret.index)
    stock_ret_df = stock_ret_df.loc[common_dates]
    nifty_aligned = nifty_ret.loc[common_dates]

    # RS = stock_return - nifty_return
    rs_df = stock_ret_df.sub(nifty_aligned, axis=0)

    # Cross-sectional percentile rank each day (across all stocks that have data)
    # rank(pct=True) gives values in (0, 1], multiply by 100
    rs_pctrank = rs_df.rank(axis=1, pct=True, na_option='keep') * 100

    return rs_pctrank


def build_signal_masks(valid_dfs, rs_pctrank, top_pct=TOP_QUARTILE_PCT,
                       bot_pct=BOTTOM_QUARTILE_PCT):
    """Build entry signal masks for all stocks, VECTORIZED.

    Signal: today's RS percentile >= top_pct AND was <= bot_pct at any
    point in the prior RECENT_LAGGARD_WINDOW bars.
    Also requires: Close > SMA(200) and turnover >= MIN_TURNOVER.

    Returns: dict of {stock_idx: boolean numpy array}.
    """
    signals = {}
    for idx, d in enumerate(valid_dfs):
        n = len(d)
        dates = d['date'].values

        # Map dates to pctrank values for this stock
        if idx not in rs_pctrank.columns:
            signals[idx] = np.zeros(n, dtype=bool)
            continue

        pctrank_col = rs_pctrank[idx]
        # Create a rank array aligned to the stock's date index
        rank_vals = pctrank_col.reindex(dates).values  # NaN where no data

        # Structural filters (vectorized)
        uptrend = (d['close'].values > d['sma_200'].values)
        liquid = (d['turnover_60d'].values >= MIN_TURNOVER)
        # Handle NaN in sma_200 / turnover
        sma_valid = np.isfinite(d['sma_200'].values)
        turn_valid = np.isfinite(d['turnover_60d'].values)
        base_filter = uptrend & liquid & sma_valid & turn_valid

        # Today in top quartile
        in_top = np.where(np.isfinite(rank_vals), rank_vals >= top_pct, False)

        # Was in bottom quartile within last RECENT_LAGGARD_WINDOW bars
        in_bottom = np.where(np.isfinite(rank_vals), rank_vals <= bot_pct, False)
        # Rolling max of in_bottom over last RECENT_LAGGARD_WINDOW bars (shifted by 1)
        # If any of the prior 15 bars was in bottom quartile, the rolling max will be True
        bottom_series = pd.Series(in_bottom.astype(float))
        was_laggard = bottom_series.shift(1).rolling(
            window=RECENT_LAGGARD_WINDOW, min_periods=1
        ).max().values.astype(bool)

        sig = base_filter & in_top & was_laggard
        # Zero out first RECENT_LAGGARD_WINDOW bars (warmup)
        sig[:RS_LOOKBACK + RECENT_LAGGARD_WINDOW] = False

        signals[idx] = sig

    return signals


def run():
    # -- Load cached panel --
    cache_path = os.path.join(CACHE_DIR, "nifty_research_150_5y.pkl")
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as fh:
            obj = pickle.load(fh)
        panel = obj['data']
        print(f"Loaded cached panel ({len(panel)} stocks, 5y)...")
    else:
        raise FileNotFoundError(f"Cache file {cache_path} not found.")

    # -- Load Nifty 50 benchmark --
    nifty_panel = get_panel([NIFTY_TICKER], period="5y", cache_name="nifty50_index_5y")
    if NIFTY_TICKER not in nifty_panel:
        raise RuntimeError("Could not download Nifty 50 index data")
    nifty_df = nifty_panel[NIFTY_TICKER].sort_values('date').reset_index(drop=True)
    print(f"Nifty 50 benchmark: {len(nifty_df)} bars loaded")

    # -- Prepare valid DataFrames --
    valid_dfs = []
    for ticker, df in panel.items():
        d = df.copy().sort_values('date').reset_index(drop=True)
        d = d.dropna(subset=['atr', 'close', 'sma_200', 'turnover_60d']).reset_index(drop=True)
        if len(d) >= 300:
            d['ticker'] = ticker
            d['is_large_cap'] = ticker in LARGE_CAPS
            valid_dfs.append(d)

    n_large = sum(1 for d in valid_dfs if d['is_large_cap'].iat[0])
    n_midsm = sum(1 for d in valid_dfs if not d['is_large_cap'].iat[0])
    print(f"Valid stocks: {len(valid_dfs)} ({n_large} large, {n_midsm} mid/small)")

    # -- Compute cross-sectional RS percentile ranks (VECTORIZED) --
    print("Computing cross-sectional relative strength ranks...")
    rs_pctrank = build_rs_matrix(valid_dfs, nifty_df)
    print(f"RS matrix: {rs_pctrank.shape[0]} dates x {rs_pctrank.shape[1]} stocks")

    # -- Build signal masks --
    print("Building signal masks...")
    sig_masks = build_signal_masks(valid_dfs, rs_pctrank)
    print("Done.\n")

    # -- Generate strategy and control trades --
    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for idx, d in enumerate(valid_dfs):
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = sig_masks[idx]
        rnd = (rng.random(len(d)) < 0.08) & liq
        strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ctrl  += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    print(f"Strategy trades: {len(strat)}")
    print(f"Control trades:  {len(ctrl)}\n")

    if len(strat) < 10:
        print("VERDICT: INSUFFICIENT TRADES. Signal fires too rarely.")
        return

    # -- Report --
    print(report(
        f"Strategy 009 - RS Rotation Q1->Q4 vs Nifty ({HORIZON}d, Costs Charged)",
        strat, ctrl, holding_days=HORIZON
    ))

    # -- Day-clustered headline (single draw) --
    dc = day_clustered_edge(strat, ctrl)
    print("\n--- DAY-CLUSTERED HEADLINE ---")
    if dc:
        print(f"  Single Draw z_paired : {dc['z_paired']:+.2f} "
              f"(day_edge: {dc['day_edge']:+.3f}%, paired days: {dc['n_paired_days']})")

    # -- Stable z_paired across 20 control seeds --
    def ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
        return c_trades

    sc = stable_day_clustered_z(strat, ctrl_factory, n_seeds=20)
    if sc:
        print(f"  Stable Mean z_paired : {sc['mean_z']:+.2f} "
              f"(min: {sc['min_z']:+.2f}, max: {sc['max_z']:+.2f}) across {sc['n_seeds']} seeds")
        print(f"  Pass Rate (z >= 2.0) : {sc['pass_rate']*100:.1f}%")

    # -- Subgroup breakdown (S8) --
    print("\n--- SUBGROUP BREAKDOWN (S8) ---")

    ms_strat, ms_ctrl = [], []
    ms_rng = np.random.default_rng(42)
    ms_indices = []
    for idx, d in enumerate(valid_dfs):
        if d['is_large_cap'].iat[0]:
            continue
        ms_indices.append(idx)
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = sig_masks[idx]
        rnd = (ms_rng.random(len(d)) < 0.08) & liq
        ms_strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        ms_ctrl += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    def ms_ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for idx in ms_indices:
            d = valid_dfs[idx]
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)
        return c_trades

    ms_res = edge_vs_control([t['net_pct'] for t in ms_strat], [t['net_pct'] for t in ms_ctrl])
    ms_sc = stable_day_clustered_z(ms_strat, ms_ctrl_factory, n_seeds=20) if len(ms_strat) >= 10 else None
    if ms_res and ms_sc:
        print(f"  Mid/Small Caps: Trades {ms_res['n_strategy']} | "
              f"Net {ms_res['strategy_avg']:+.2f}% | Edge {ms_res['edge']:+.2f}% | "
              f"Stable mean_z: {ms_sc['mean_z']:+.2f} (Pass: {ms_sc['pass_rate']*100:.0f}%)")
    elif ms_res:
        ms_dc = day_clustered_edge(ms_strat, ms_ctrl)
        z_str = f"z_paired {ms_dc['z_paired']:+.2f}" if ms_dc else "n/a"
        print(f"  Mid/Small Caps: Trades {ms_res['n_strategy']} | "
              f"Net {ms_res['strategy_avg']:+.2f}% | Edge {ms_res['edge']:+.2f}% | {z_str}")
    else:
        print(f"  Mid/Small Caps: {len(ms_strat)} trades (insufficient)")

    lc_strat, lc_ctrl = [], []
    lc_rng = np.random.default_rng(42)
    for idx, d in enumerate(valid_dfs):
        if not d['is_large_cap'].iat[0]:
            continue
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = sig_masks[idx]
        rnd = (lc_rng.random(len(d)) < 0.08) & liq
        lc_strat += simulate_trades(d, sig, horizon_days=HORIZON, charge_costs=True)
        lc_ctrl += simulate_trades(d, rnd, horizon_days=HORIZON, charge_costs=True)

    lc_res = edge_vs_control([t['net_pct'] for t in lc_strat], [t['net_pct'] for t in lc_ctrl])
    if lc_res:
        lc_dc = day_clustered_edge(lc_strat, lc_ctrl)
        z_str = f"z_paired {lc_dc['z_paired']:+.2f}" if lc_dc else "n/a"
        print(f"  Large Caps:     Trades {lc_res['n_strategy']} | "
              f"Net {lc_res['strategy_avg']:+.2f}% | Edge {lc_res['edge']:+.2f}% | {z_str}")
    else:
        print(f"  Large Caps:     {len(lc_strat)} trades (insufficient)")

    # -- Walk-forward validation --
    sample_len = len(valid_dfs[0])
    splits = list(walk_forward_splits(sample_len, n_splits=4, horizon_days=HORIZON))
    print(f"\n--- WALK-FORWARD ({len(splits)} purged folds) ---")
    for fold_idx, ((tr0, tr1), (te0, te1)) in enumerate(splits, 1):
        f_rng = np.random.default_rng(42 + fold_idx)
        f_strat, f_ctrl = [], []
        for idx, d in enumerate(valid_dfs):
            test_df = d.iloc[te0:te1].reset_index(drop=True)
            if len(test_df) < HORIZON + 2:
                continue
            liq = (test_df['turnover_60d'] >= MIN_TURNOVER).fillna(False).values

            # Use the pre-computed full-sample pct_ranks (no look-ahead: rank on day T
            # uses only close prices up to day T)
            test_dates = test_df['date'].values
            if idx not in rs_pctrank.columns:
                rnd = (f_rng.random(len(test_df)) < 0.08) & liq
                f_ctrl += simulate_trades(test_df, rnd, horizon_days=HORIZON, charge_costs=True)
                continue
            rank_vals = rs_pctrank[idx].reindex(test_dates).values
            uptrend = (test_df['close'].values > test_df['sma_200'].values)
            sma_ok = np.isfinite(test_df['sma_200'].values)
            turn_ok = np.isfinite(test_df['turnover_60d'].values)
            base_f = uptrend & liq & sma_ok & turn_ok
            in_top = np.where(np.isfinite(rank_vals), rank_vals >= TOP_QUARTILE_PCT, False)
            in_bottom = np.where(np.isfinite(rank_vals), rank_vals <= BOTTOM_QUARTILE_PCT, False)
            was_lag = pd.Series(in_bottom.astype(float)).shift(1).rolling(
                window=RECENT_LAGGARD_WINDOW, min_periods=1).max().values.astype(bool)
            sig = base_f & in_top & was_lag
            sig[:min(RS_LOOKBACK + RECENT_LAGGARD_WINDOW, len(sig))] = False

            rnd = (f_rng.random(len(test_df)) < 0.08) & liq
            f_strat += simulate_trades(test_df, sig, horizon_days=HORIZON, charge_costs=True)
            f_ctrl += simulate_trades(test_df, rnd, horizon_days=HORIZON, charge_costs=True)

        f_res = edge_vs_control([t['net_pct'] for t in f_strat], [t['net_pct'] for t in f_ctrl])
        f_dc = day_clustered_edge(f_strat, f_ctrl)
        d_start = valid_dfs[0]['date'].iat[min(te0, sample_len-1)].strftime('%Y-%m-%d')
        d_end = valid_dfs[0]['date'].iat[min(te1-1, sample_len-1)].strftime('%Y-%m-%d')
        if f_res and f_dc:
            print(f"  Fold {fold_idx} ({d_start} to {d_end}): "
                  f"Trades {f_res['n_strategy']:4d} | Net {f_res['strategy_avg']:+5.2f}% | "
                  f"Edge {f_res['edge']:+5.2f}% | z_paired {f_dc['z_paired']:+5.2f}")
        else:
            print(f"  Fold {fold_idx} ({d_start} to {d_end}): "
                  f"Trades {len(f_strat):4d} -- insufficient for paired analysis")

    # -- Sensitivity (robustness, not a search) --
    print("\n--- PARAMETER SENSITIVITY ---")
    for desc, top_pct, bot_pct in [
        ("Tighter Q (80/20)", 80, 20),
        ("PRIMARY (75/25)", TOP_QUARTILE_PCT, BOTTOM_QUARTILE_PCT),
        ("Wider Q (70/30)", 70, 30),
    ]:
        sens_masks = build_signal_masks(valid_dfs, rs_pctrank, top_pct=top_pct, bot_pct=bot_pct)
        sens_strat = []
        for idx, d in enumerate(valid_dfs):
            sens_strat += simulate_trades(d, sens_masks[idx], horizon_days=HORIZON, charge_costs=True)
        sens_res = edge_vs_control([t['net_pct'] for t in sens_strat], [t['net_pct'] for t in ctrl])
        sens_dc = day_clustered_edge(sens_strat, ctrl)
        if sens_res and sens_dc:
            print(f"  {desc:20s}: Trades {sens_res['n_strategy']:4d} | "
                  f"Net {sens_res['strategy_avg']:+5.2f}% | Edge {sens_res['edge']:+5.2f}% | "
                  f"z_paired {sens_dc['z_paired']:+5.2f}")
        else:
            print(f"  {desc:20s}: {len(sens_strat)} trades -- insufficient")

    # -- Final verdict --
    print("\n" + "="*70)
    print("VERDICT GUIDE")
    print("="*70)
    if sc:
        if sc['mean_z'] >= 2.0 and sc['pass_rate'] >= 0.80:
            print(f"  Stable mean_z {sc['mean_z']:.2f}, pass rate {sc['pass_rate']*100:.0f}% -> "
                  "CLEARS the bar on pooled. Check subgroup + walk-forward before adopting.")
        elif sc['mean_z'] >= 2.0:
            print(f"  Stable mean_z {sc['mean_z']:.2f} but pass rate only {sc['pass_rate']*100:.0f}% -> "
                  "BORDERLINE. Likely INCONCLUSIVE.")
        else:
            print(f"  Stable mean_z {sc['mean_z']:.2f} < 2.0 -> REJECT.")


if __name__ == "__main__":
    run()
