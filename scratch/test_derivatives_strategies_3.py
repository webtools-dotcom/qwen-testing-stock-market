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

FO_TICKERS = {
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
}

MIN_TURNOVER = 25e7

# Compute panel market return (Nifty / broad market proxy)
all_dfs = []
for t, df in panel.items():
    if t in FO_TICKERS:
        df = df.copy()
        df['ticker'] = t
        all_dfs.append(df[['date', 'ticker', 'close', 'open', 'high', 'low', 'volume']])

concat_df = pd.concat(all_dfs, ignore_index=True)
concat_df['daily_ret'] = concat_df.groupby('ticker')['close'].pct_change() * 100
market_daily = concat_df.groupby('date')['daily_ret'].mean().rename('fo_mkt_ret')

processed = {}
for ticker, df in panel.items():
    if ticker not in FO_TICKERS:
        continue
    d = df.copy().sort_values('date').reset_index(drop=True)
    d = d.merge(market_daily, on='date', how='left')
    d['ticker'] = ticker
    
    # 5-day and 10-day relative drawdowns vs F&O market
    d['daily_ret'] = d['close'].pct_change() * 100
    d['ret_5d'] = d['close'].pct_change(5) * 100
    d['fo_mkt_ret_5d'] = d['fo_mkt_ret'].rolling(5).sum()
    d['rel_drawdown_5d'] = d['ret_5d'] - d['fo_mkt_ret_5d']
    
    # ATR stretch: distance from 20 EMA in terms of ATR
    d['ema_20'] = ta.trend.EMAIndicator(close=d['close'], window=20).ema_indicator()
    d['atr_stretch'] = (d['close'] - d['ema_20']) / d['atr']
    
    # Volume relative
    d['vol_med_20'] = d['volume'].rolling(20).median()
    d['vol_ratio'] = d['volume'] / d['vol_med_20']
    
    # Setup 10: Severe Relative Underperformance in F&O (Stock down > 6% more than F&O index in 5 days)
    d['fno_rel_underperf'] = (d['rel_drawdown_5d'] < -6.0) & (d['close'] > d['sma_200']) & (d['rsi'] < 35)
    
    # Setup 11: 2.5x ATR Downside Stretch in Uptrend (Close < EMA20 - 2.5*ATR)
    d['fno_atr_stretch'] = (d['atr_stretch'] < -2.5) & (d['close'] > d['sma_200'])
    
    # Setup 12: High-Volume Reversal Bar in Oversold F&O (RSI < 35, Close > Open + 1.5%, Vol > 1.8x)
    d['fno_bullish_engulf_vol'] = (d['rsi'].shift(1) < 35) & (d['close'] > d['open'] * 1.015) & (d['vol_ratio'] > 1.8) & (d['close'] > d['sma_200'])

    d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'atr_stretch', 'rel_drawdown_5d', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Processed {len(processed)} F&O stocks.")

def test_strat(name, signal_fn, horizon=7):
    print(f"\n=======================================================")
    print(f"Testing: {name} (Horizon {horizon}d)")
    print(f"=======================================================")
    
    rng = np.random.default_rng(42)
    strat, ctrl = [], []
    for ticker, d in processed.items():
        liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
        sig = signal_fn(d) & liq
        rnd = (rng.random(len(d)) < 0.08) & liq
        strat += simulate_trades(d, sig, horizon_days=horizon, charge_costs=True)
        ctrl += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        
    naive = edge_vs_control([t['net_pct'] for t in strat], [t['net_pct'] for t in ctrl])
    dc = day_clustered_edge(strat, ctrl)
    
    if not naive or not dc:
        print("  Insufficient trades.")
        return
        
    print(f"  Seed 42 Draw: Trades {naive['n_strategy']} | PairedDays {dc['n_paired_days']} | "
          f"Net {naive['strategy_avg']:+.2f}% | Edge {naive['edge']:+.2f}% | "
          f"Naive-z {naive['z']:.2f} | z_paired {dc['z_paired']:.2f} | DayEdge {dc['day_edge']:+.2f}%")
          
    def control_factory(seed):
        c_rng = np.random.default_rng(seed)
        c_trades = []
        for ticker, d in processed.items():
            liq = (d['turnover_60d'] >= MIN_TURNOVER).fillna(False).values
            rnd = (c_rng.random(len(d)) < 0.08) & liq
            c_trades += simulate_trades(d, rnd, horizon_days=horizon, charge_costs=True)
        return c_trades

    stable = stable_day_clustered_z(strat, control_factory, n_seeds=20)
    if stable:
        print(f"  STABLE 20-SEED CONTROL: mean_z = {stable['mean_z']:.2f} | min_z = {stable['min_z']:.2f} | "
              f"max_z = {stable['max_z']:.2f} | pass_rate (>=2.0) = {stable['pass_rate']*100:.1f}%")

test_strat("10. Relative Underperformance Washout in F&O", lambda d: d['fno_rel_underperf'], horizon=7)
test_strat("11. 2.5x ATR Downside Stretch in F&O Uptrend", lambda d: d['fno_atr_stretch'], horizon=7)
test_strat("12. High-Volume Reversal Bar in Oversold F&O", lambda d: d['fno_bullish_engulf_vol'], horizon=7)
