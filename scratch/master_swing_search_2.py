import sys, os
sys.path.insert(0, r"d:\nabop\backtesting-unique-strategies")

import pickle
import numpy as np
import pandas as pd
import ta
from data_loader import CACHE_DIR, get_panel
from backtest_engine import (
    simulate_trades, edge_vs_control, day_clustered_edge,
    stable_day_clustered_z, walk_forward_splits, report
)

path = os.path.join(CACHE_DIR, "nifty_research_150_5y.pkl")
with open(path, 'rb') as fh:
    obj = pickle.load(fh)
panel = obj['data']

MIN_TURNOVER = 25e7

LARGE_CAPS = {
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'AXISBANK.NS',
    'LT.NS', 'ITC.NS', 'HINDUNILVR.NS', 'MARUTI.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS',
    'SUNPHARMA.NS', 'CIPLA.NS', 'DRREDDY.NS', 'WIPRO.NS', 'TECHM.NS', 'HCLTECH.NS', 'BAJFINANCE.NS',
    'ASIANPAINT.NS', 'ULTRACEMCO.NS', 'GRASIM.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS',
    'ADANIPORTS.NS', 'TITAN.NS', 'NESTLEIND.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'EICHERMOT.NS',
    'BAJAJ-AUTO.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS', 'BPCL.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'INDUSINDBK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'SBILIFE.NS', 'SHRIRAMFIN.NS', 'TRENT.NS', 'APOLLOHOSP.NS'
}

processed = {}
for ticker, df in panel.items():
    d = df.copy().sort_values('date').reset_index(drop=True)
    d['ticker'] = ticker
    d['is_large_cap'] = ticker in LARGE_CAPS

    d['ema_20'] = ta.trend.EMAIndicator(close=d['close'], window=20).ema_indicator()
    d['ema_10'] = ta.trend.EMAIndicator(close=d['close'], window=10).ema_indicator()
    d['vol_med_20'] = d['volume'].rolling(20).median()
    d['vol_ratio'] = d['volume'] / d['vol_med_20'].replace(0, np.nan)
    d['daily_ret'] = d['close'].pct_change() * 100

    # RSI 2
    d['rsi_2'] = ta.momentum.RSIIndicator(close=d['close'], window=2).rsi()

    # Bollinger & Keltner Squeeze
    bb = ta.volatility.BollingerBands(close=d['close'], window=20, window_dev=2)
    d['bb_upper'] = bb.bollinger_hband()
    d['bb_lower'] = bb.bollinger_lband()
    d['keltner_upper_15'] = d['ema_20'] + 1.5 * d['atr']
    d['keltner_lower_15'] = d['ema_20'] - 1.5 * d['atr']

    d['squeeze_bb_keltner'] = (d['bb_upper'] < d['keltner_upper_15']) & (d['bb_lower'] > d['keltner_lower_15'])
    d['sig_squeeze_breakout'] = d['squeeze_bb_keltner'].shift(1) & (d['close'] > d['bb_upper']) & (d['vol_ratio'] > 1.8) & (d['close'] > d['sma_200'])

    # Bullish RSI Divergence (Price lower low over 10d, RSI higher low over 10d)
    price_ll = d['low'] < d['low'].shift(10)
    rsi_hl = d['rsi'] > d['rsi'].shift(10)
    d['sig_rsi_bull_div'] = price_ll & rsi_hl & (d['rsi'] < 42) & (d['close'] > d['sma_200']) & (d['close'] > d['open'])

    # RSI(2) extreme oversold in 20 EMA trend
    d['sig_rsi2_extreme'] = (d['rsi_2'] < 8.0) & (d['close'] > d['ema_20']) & (d['close'] > d['sma_200'])

    # 10 EMA Touch & Engulf in Momentum Leaders (Mom60 > 15%)
    d['touch_ema10'] = (d['low'] <= d['ema_10']) & (d['close'] > d['ema_10'])
    d['engulf'] = (d['close'] > d['high'].shift(1)) & (d['close'] > d['open'])
    d['sig_ema10_engulf'] = d['touch_ema10'] & d['engulf'] & (d['momentum_60d'] > 15.0) & (d['close'] > d['sma_200'])

    # Gap Down Absorption Reversal (Gap < -1.2*ATR, recovers > 60% of daily range, vol > 2x)
    gap_down = d['open'] < d['close'].shift(1) - 1.2 * d['atr']
    strong_close = (d['close'] - d['low']) / (d['high'] - d['low']).replace(0, np.nan) > 0.65
    d['sig_gap_down_absorption'] = gap_down & strong_close & (d['vol_ratio'] > 2.0) & (d['close'] > d['sma_200'])

    # Low-Volume Retest of 20-day High
    prev_20h = d['high'].rolling(20).max().shift(2)
    retest = (d['low'] <= prev_20h * 1.01) & (d['close'] >= prev_20h * 0.99)
    low_vol = d['vol_ratio'] < 0.8
    d['sig_retest_20h_lowvol'] = retest & low_vol & (d['close'] > d['sma_200']) & (d['close'] > d['open'])

    d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Loaded {len(processed)} processed stocks for batch 2.")

def eval_strategy(name, signal_fn, horizon=7):
    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    valid_dfs = []

    for ticker, d in processed.items():
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_fn(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq

        strat_t = simulate_trades(d, sig, horizon_days=horizon, charge_costs=True)
        ctrl_t = simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        strat += strat_t
        ctrl += ctrl_t
        valid_dfs.append(d)

    res = edge_vs_control([t['net_pct'] for t in strat], [t['net_pct'] for t in ctrl])
    dc = day_clustered_edge(strat, ctrl)

    if res is None or dc is None or len(strat) < 15:
        print(f"[{name:58s}] INSUFFICIENT TRADES (trades={len(strat)})")
        return None

    def ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return c_trades

    sc = stable_day_clustered_z(strat, ctrl_factory, n_seeds=20)

    # Subgroup Mid/Small check (§8)
    ms_strat, ms_ctrl = [], []
    ms_indices = []
    for idx, d in enumerate(valid_dfs):
        if d['is_large_cap'].iat[0]:
            continue
        ms_indices.append(idx)
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_fn(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        ms_strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True)
        ms_ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)

    def ms_ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for idx in ms_indices:
            d = valid_dfs[idx]
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return c_trades

    ms_sc = stable_day_clustered_z(ms_strat, ms_ctrl_factory, n_seeds=20) if len(ms_strat) >= 10 else None

    # Walk forward
    sample_len = len(valid_dfs[0])
    splits = list(walk_forward_splits(sample_len, n_splits=4, horizon_days=horizon))
    wf_folds = []
    for fold_idx, ((tr0, tr1), (te0, te1)) in enumerate(splits, 1):
        f_rng = np.random.default_rng(42 + fold_idx)
        f_strat, f_ctrl = [], []
        for d in valid_dfs:
            test_df = d.iloc[te0:te1].reset_index(drop=True)
            if len(test_df) < horizon + 2:
                continue
            liq = (test_df['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            sig = signal_fn(test_df) & liq
            rnd = (f_rng.random(len(test_df)) < 0.08) & liq
            f_strat += simulate_trades(test_df, sig, horizon_days=horizon, charge_costs=True)
            f_ctrl += simulate_trades(test_df, rnd, horizon_days=horizon, charge_costs=True)
        f_dc = day_clustered_edge(f_strat, f_ctrl)
        f_res = edge_vs_control([t['net_pct'] for t in f_strat], [t['net_pct'] for t in f_ctrl])
        if f_dc and f_res:
            wf_folds.append((fold_idx, f_res['n_strategy'], f_res['strategy_avg'], f_dc['z_paired']))
        else:
            wf_folds.append((fold_idx, 0, 0.0, 0.0))

    mean_z = sc['mean_z'] if sc else 0.0
    pass_r = sc['pass_rate'] * 100 if sc else 0.0
    ms_mean_z = ms_sc['mean_z'] if ms_sc else 0.0
    ms_pass_r = ms_sc['pass_rate'] * 100 if ms_sc else 0.0
    f4_z = wf_folds[-1][3] if wf_folds else 0.0
    f4_net = wf_folds[-1][2] if wf_folds else 0.0

    print(f"[{name:58s}] Tr={res['n_strategy']:3d} | Net={res['strategy_avg']:+5.2f}% | Edge={res['edge']:+5.2f}% | "
          f"StableZ={mean_z:+5.2f} ({pass_r:3.0f}%) | MS_Z={ms_mean_z:+5.2f} ({ms_pass_r:3.0f}%) | F4_z={f4_z:+5.2f}")
    return {
        'name': name, 'trades': res['n_strategy'], 'net': res['strategy_avg'], 'edge': res['edge'],
        'mean_z': mean_z, 'pass_rate': pass_r, 'ms_mean_z': ms_mean_z, 'ms_pass_rate': ms_pass_r,
        'wf_folds': wf_folds
    }

print("\n" + "="*135)
print("MASTER SWING SEARCH BATCH 2")
print("="*135)

eval_strategy("1. BB in Keltner Squeeze Breakout (8d)",
              lambda d: d['sig_squeeze_breakout'], horizon=8)

eval_strategy("2. Bullish RSI Divergence in Uptrend (7d)",
              lambda d: d['sig_rsi_bull_div'], horizon=7)

eval_strategy("3. RSI(2) Extreme Oversold (<8) in 20 EMA Trend (6d)",
              lambda d: d['sig_rsi2_extreme'], horizon=6)

eval_strategy("4. 10 EMA Touch & Engulf in Momentum Leaders (8d)",
              lambda d: d['sig_ema10_engulf'], horizon=8)

eval_strategy("5. Gap Down Absorption Reversal in Uptrend (6d)",
              lambda d: d['sig_gap_down_absorption'], horizon=6)

eval_strategy("6. Low-Volume Retest of 20-day High (8d)",
              lambda d: d['sig_retest_20h_lowvol'], horizon=8)
