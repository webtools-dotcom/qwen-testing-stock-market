import sys, os
sys.path.insert(0, r"d:\nabop\backtesting-unique-strategies")

import pickle
import numpy as np
import pandas as pd
import ta
import yfinance as yf
from data_loader import CACHE_DIR, get_panel
from backtest_engine import (
    simulate_trades, edge_vs_control, day_clustered_edge,
    stable_day_clustered_z, walk_forward_splits, report
)

# Load cached 150-stock panel
path = os.path.join(CACHE_DIR, "nifty_research_150_5y.pkl")
if os.path.exists(path):
    with open(path, 'rb') as fh:
        obj = pickle.load(fh)
    panel = obj['data']
else:
    raise FileNotFoundError(f"Cache file {path} not found")

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

# Fetch Nifty index for relative indicators
nifty_panel = get_panel(["^NSEI"], period="5y", cache_name="nifty50_index_5y")
nifty_df = nifty_panel["^NSEI"].sort_values('date').reset_index(drop=True)
nifty_df['nifty_ret_20'] = nifty_df['close'].pct_change(20) * 100

processed = {}
for ticker, df in panel.items():
    d = df.copy().sort_values('date').reset_index(drop=True)
    d['ticker'] = ticker
    d['is_large_cap'] = ticker in LARGE_CAPS
    d = d.merge(nifty_df[['date', 'nifty_ret_20']], on='date', how='left')

    # Basic indicators
    d['ema_20'] = ta.trend.EMAIndicator(close=d['close'], window=20).ema_indicator()
    d['ema_10'] = ta.trend.EMAIndicator(close=d['close'], window=10).ema_indicator()
    d['vol_med_20'] = d['volume'].rolling(20).median()
    d['vol_ratio'] = d['volume'] / d['vol_med_20'].replace(0, np.nan)
    d['daily_ret'] = d['close'].pct_change() * 100
    d['roc_5'] = d['close'].pct_change(5) * 100
    d['roc_10'] = d['close'].pct_change(10) * 100
    d['roc_20'] = d['close'].pct_change(20) * 100

    # RS vs Nifty
    d['rs_20'] = d['roc_20'] - d['nifty_ret_20']

    # Keltner channels (20 EMA, 2.0 ATR)
    d['keltner_lower'] = d['ema_20'] - 2.0 * d['atr']
    d['keltner_upper'] = d['ema_20'] + 2.0 * d['atr']

    # ADX / DMI
    adx_ind = ta.trend.ADXIndicator(high=d['high'], low=d['low'], close=d['close'], window=14)
    d['adx'] = adx_ind.adx()
    d['adx_pos'] = adx_ind.adx_pos()
    d['adx_neg'] = adx_ind.adx_neg()

    # RSI Velocity (3-day change)
    d['rsi_vel_3'] = d['rsi'] - d['rsi'].shift(3)

    # 1. Keltner Lower Band Rebound in Uptrend
    # Touch lower band (Low <= lower), Close > lower, Close > Open, Close > 200 SMA
    d['sig_keltner_rebound'] = (d['low'] <= d['keltner_lower']) & (d['close'] > d['keltner_lower']) & (d['close'] > d['open']) & (d['close'] > d['sma_200'])

    # 2. ADX Squeeze Breakout (+DI cross -DI when ADX < 20, Vol > 1.5x)
    d['sig_adx_squeeze_breakout'] = (d['adx'].shift(1) < 20.0) & (d['adx_pos'] > d['adx_neg']) & (d['adx_pos'].shift(1) <= d['adx_neg'].shift(1)) & (d['vol_ratio'] > 1.5) & (d['close'] > d['sma_200'])

    # 3. 3-Day RSI Velocity Washout in Mid/Small Caps (RSI drops > 15 in 3d, RSI < 33, Close > 200 SMA)
    d['sig_rsi_vel_washout_ms'] = (d['rsi_vel_3'] < -15.0) & (d['rsi'] < 33) & (d['close'] > d['sma_200']) & (~d['is_large_cap'])

    # 4. Wyckoff 50-SMA Liquidity Sweep / Spring
    d['sig_spring_50sma'] = (d['low'] < d['sma_50']) & (d['close'] > d['sma_50']) & (d['close'] > d['open']) & (d['vol_ratio'] > 1.3) & (d['sma_50'] > d['sma_200']) & (d['close'] > d['sma_200'])

    # 5. Relative Strength Divergence (Stock 20d low, RS 20d high)
    # Stock low <= 20-day min low, but RS_20 > RS_20 10 days ago + 5%, Close > 200 SMA
    d['stock_20d_low'] = d['close'] <= d['close'].rolling(20).min()
    d['rs_rising'] = d['rs_20'] > d['rs_20'].shift(10) + 5.0
    d['sig_rs_divergence'] = d['stock_20d_low'] & d['rs_rising'] & (d['close'] > d['sma_200']) & (d['close'] > d['open'])

    # 6. Volatility Contraction (ATR% low) + Volume Thrust Breakout
    d['atr_pct_low'] = d['atr_pct'] < d['atr_pct'].rolling(60).quantile(0.20)
    d['sig_vcp_thrust'] = d['atr_pct_low'].shift(1) & (d['close'] > d['high'].rolling(10).max().shift(1)) & (d['vol_ratio'] > 1.8) & (d['close'] > d['sma_200'])

    # 7. 3-Day Downside Accelerating Climax in Uptrend
    d['sig_accel_climax'] = (d['daily_ret'] < d['daily_ret'].shift(1)) & (d['daily_ret'].shift(1) < d['daily_ret'].shift(2)) & (d['daily_ret'].shift(2) < 0) & (d['roc_5'] < -6.0) & (d['close'] > d['sma_200'])

    # 8. 10-day RoC Oversold in Mid/Small Caps with Trend Gate & Bullish Rejection
    d['sig_roc10_ms_gated'] = (d['roc_10'] < -8.0) & (d['rsi'] < 35) & (d['close'] > d['sma_200']) & (d['close'] > d['open']) & (~d['is_large_cap'])

    d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'sma_50', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Loaded {len(processed)} processed stocks.")

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
print("MASTER SWING STRATEGY SEARCH (6-10 DAY HOLDING PERIOD)")
print("="*135)

eval_strategy("1. Keltner Lower Band Rebound in 200 SMA Uptrend (7d)",
              lambda d: d['sig_keltner_rebound'], horizon=7)

eval_strategy("2. ADX Squeeze Breakout + Volume > 1.5x in Uptrend (8d)",
              lambda d: d['sig_adx_squeeze_breakout'], horizon=8)

eval_strategy("3. 3-Day RSI Velocity Washout in Mid/Small Caps (7d)",
              lambda d: d['sig_rsi_vel_washout_ms'], horizon=7)

eval_strategy("4. Wyckoff 50-SMA Spring / Liquidity Sweep (8d)",
              lambda d: d['sig_spring_50sma'], horizon=8)

eval_strategy("5. Relative Strength Divergence (Stock 20d low, RS high) (8d)",
              lambda d: d['sig_rs_divergence'], horizon=8)

eval_strategy("6. VCP ATR Squeeze + Donchian Volume Thrust Breakout (8d)",
              lambda d: d['sig_vcp_thrust'], horizon=8)

eval_strategy("7. 3-Day Downside Accelerating Climax in Uptrend (7d)",
              lambda d: d['sig_accel_climax'], horizon=7)

eval_strategy("8. 10-day RoC Oversold in Mid/Small Caps + Bullish Close (8d)",
              lambda d: d['sig_roc10_ms_gated'], horizon=8)
