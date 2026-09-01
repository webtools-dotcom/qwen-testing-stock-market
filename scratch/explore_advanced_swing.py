import sys, os
sys.path.insert(0, r"d:\nabop\backtesting-unique-strategies")

import pickle
import numpy as np
import pandas as pd
import ta
import yfinance as yf
from data_loader import CACHE_DIR
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

# Fetch Nifty 50 benchmark index data
nifty_raw = yf.download("^NSEI", period="5y", interval="1d", auto_adjust=True, progress=False)
if isinstance(nifty_raw.columns, pd.MultiIndex):
    nifty_raw.columns = nifty_raw.columns.get_level_values(0)
nifty_df = pd.DataFrame({
    'date': pd.to_datetime(nifty_raw.index),
    'nifty_close': nifty_raw['Close'].values
}).sort_values('date').reset_index(drop=True)
nifty_df['nifty_sma200'] = nifty_df['nifty_close'].rolling(200).mean()
nifty_df['nifty_ret_63'] = nifty_df['nifty_close'].pct_change(63) * 100
nifty_df['nifty_ret_21'] = nifty_df['nifty_close'].pct_change(21) * 100

processed = {}
for ticker, df in panel.items():
    d = df.copy().sort_values('date').reset_index(drop=True)
    d['ticker'] = ticker
    d['is_large_cap'] = ticker in LARGE_CAPS
    d = d.merge(nifty_df, on='date', how='left')
    
    # 20 EMA, 50 SMA, 200 SMA
    d['ema_20'] = ta.trend.EMAIndicator(close=d['close'], window=20).ema_indicator()
    d['ema_10'] = ta.trend.EMAIndicator(close=d['close'], window=10).ema_indicator()
    
    # Relative Strength vs Nifty
    d['stock_ret_63'] = d['close'].pct_change(63) * 100
    d['stock_ret_21'] = d['close'].pct_change(21) * 100
    d['rs_63'] = d['stock_ret_63'] - d['nifty_ret_63']
    d['rs_21'] = d['stock_ret_21'] - d['nifty_ret_21']
    
    # Range / Volume
    d['vol_med_20'] = d['volume'].rolling(20).median()
    d['vol_ratio'] = d['volume'] / d['vol_med_20'].replace(0, np.nan)
    d['range'] = d['high'] - d['low']
    d['body'] = (d['close'] - d['open']).abs()
    
    # Pullback to 20 EMA: Low <= 1.005 * EMA20 and Close >= EMA20
    d['touch_ema20'] = (d['low'] <= 1.005 * d['ema_20']) & (d['close'] >= 0.995 * d['ema_20'])
    
    # 3-day pullback into 20 EMA in RS leader:
    # 63d RS > 15% (outperforming Nifty by >15% over 3 months), Close > SMA200, Nifty > Nifty SMA200
    d['rs_leader'] = (d['rs_63'] > 15.0) & (d['close'] > d['sma_200']) & (d['sma_50'] > d['sma_200'])
    
    # Rejection at 20 EMA: Touched 20 EMA and printed green candle (Close > Open)
    d['ema20_rejection_green'] = d['touch_ema20'] & (d['close'] > d['open']) & d['rs_leader']
    
    # Rejection at 20 EMA with Volume > 1.2x
    d['ema20_rejection_vol'] = d['ema20_rejection_green'] & (d['vol_ratio'] > 1.2)
    
    # 52-week High Pullback (within 15% of 52-week High, pulled back 5-10% to 20 EMA)
    d['high_252'] = d['close'].rolling(252).max()
    d['dist_52w_high'] = (d['close'] / d['high_252'] - 1) * 100
    d['near_52w_high'] = (d['dist_52w_high'] >= -15.0)
    
    # Setup: 52-week high momentum pullback to 20 EMA
    d['mom_52w_ema20_pullback'] = d['near_52w_high'] & d['touch_ema20'] & (d['close'] > d['open']) & (d['close'] > d['sma_200'])

    # Setup: 3-day high volume thrust breakout out of 20-day high (stage 2 base breakout)
    d['breakout_20d_high'] = (d['close'] > d['high'].rolling(20).max().shift(1)) & (d['vol_ratio'] > 2.0) & (d['close'] > d['sma_200']) & (d['close'] > d['open'])

    # Setup: Donchian 20-day Channel Re-test (Price broke out within last 5 days, now retesting 20d High)
    d['high_20_prev'] = d['high'].rolling(20).max().shift(1)
    d['retest_20d_high'] = (d['low'] <= d['high_20_prev'] * 1.01) & (d['close'] >= d['high_20_prev'] * 0.99) & (d['close'] > d['open']) & (d['close'] > d['sma_200'])

    # Setup: MACD Histogram Bullish Divergence in Uptrend
    # Stock makes lower low over 10 days, but MACD histogram makes higher low
    d['macd_hist'] = d['macd'] - d['macd_signal']
    d['price_lower_low'] = d['low'] < d['low'].shift(5)
    d['macd_higher_low'] = d['macd_hist'] > d['macd_hist'].shift(5)
    d['macd_div'] = d['price_lower_low'] & d['macd_higher_low'] & (d['macd_hist'] < 0) & (d['close'] > d['sma_200']) & (d['close'] > d['open'])

    d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'ema_20', 'rs_63', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Loaded {len(processed)} stocks with relative strength and multi-timeframe indicators.")

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
        print(f"[{name:52s}] INSUFFICIENT TRADES (trades={len(strat)})")
        return None
    
    def ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for d in valid_dfs:
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return c_trades
    
    sc = stable_day_clustered_z(strat, ctrl_factory, n_seeds=15)
    
    # Subgroup Mid/Small check (§8)
    ms_strat, ms_ctrl = [], []
    for ticker, d in processed.items():
        if d['is_large_cap'].iat[0]:
            continue
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_fn(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        ms_strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True)
        ms_ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        
    def ms_ctrl_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for ticker, d in processed.items():
            if d['is_large_cap'].iat[0]:
                continue
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return c_trades
        
    ms_sc = stable_day_clustered_z(ms_strat, ms_ctrl_factory, n_seeds=15) if len(ms_strat) >= 10 else None
    
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
    
    print(f"[{name:52s}] Tr={res['n_strategy']:3d} | Net={res['strategy_avg']:+5.2f}% | Edge={res['edge']:+5.2f}% | "
          f"StableZ={mean_z:+5.2f} ({pass_r:3.0f}%) | MS_Z={ms_mean_z:+5.2f} ({ms_pass_r:3.0f}%) | F4_z={f4_z:+5.2f}")
    return {
        'name': name, 'trades': res['n_strategy'], 'net': res['strategy_avg'], 'edge': res['edge'],
        'mean_z': mean_z, 'pass_rate': pass_r, 'ms_mean_z': ms_mean_z, 'wf_folds': wf_folds
    }

print("\n" + "="*120)
print("TESTING ADVANCED SWING HYPOTHESES")
print("="*120)

eval_strategy("A. 20 EMA Rejection in RS Leaders (RS_63 > 15%, Close>Open)",
              lambda d: d['ema20_rejection_green'], horizon=7)

eval_strategy("B. 20 EMA Rejection + Vol > 1.2x in RS Leaders",
              lambda d: d['ema20_rejection_vol'], horizon=7)

eval_strategy("C. Near 52-week High Pullback to 20 EMA + Green",
              lambda d: d['mom_52w_ema20_pullback'], horizon=7)

eval_strategy("D. 20-day High Breakout + Vol > 2.0x in Uptrend",
              lambda d: d['breakout_20d_high'], horizon=7)

eval_strategy("E. 20-day High Retest Bounce in Uptrend",
              lambda d: d['retest_20d_high'], horizon=7)

eval_strategy("F. MACD Bullish Divergence in 200 SMA Uptrend",
              lambda d: d['macd_div'], horizon=7)
