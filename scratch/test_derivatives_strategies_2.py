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

processed = {}
for ticker, df in panel.items():
    if ticker not in FO_TICKERS:
        continue
    d = df.copy().sort_values('date').reset_index(drop=True)
    d['ticker'] = ticker
    
    # Realized Volatility: 10d std vs 60d std
    d['ret_1d'] = d['close'].pct_change()
    d['rv_10'] = d['ret_1d'].rolling(10).std()
    d['rv_60'] = d['ret_1d'].rolling(60).std()
    d['rv_ratio'] = d['rv_10'] / d['rv_60']
    
    # Expiry calendar logic
    d['day'] = d['date'].dt.day
    d['day_of_week'] = d['date'].dt.dayofweek # 3 = Thu, 4 = Fri
    d['days_in_month'] = d['date'].dt.days_in_month
    # Expiry week: last 7 days of month
    d['is_expiry_week'] = d['day'] >= (d['days_in_month'] - 7)
    d['is_post_expiry'] = (d['day'] <= 5)
    
    d['roc_5'] = d['close'].pct_change(5) * 100
    d['roc_10'] = d['close'].pct_change(10) * 100
    d['vol_med_20'] = d['volume'].rolling(20).median()
    d['vol_ratio'] = d['volume'] / d['vol_med_20']
    d['down_3d'] = (d['close'] < d['close'].shift(1)) & (d['close'].shift(1) < d['close'].shift(2)) & (d['close'].shift(2) < d['close'].shift(3))
    
    # Setup A: Post-Expiry Oversold Bounce (Oversold into expiry, buy in first 3 days of new series)
    d['post_expiry_oversold'] = d['is_post_expiry'] & (d['roc_10'] < -6.0) & (d['close'] > d['sma_200'])
    
    # Setup B: Expiry Week Capitulation (Last 7 days of month, drop > 5% on high volume)
    d['expiry_week_capitulation'] = d['is_expiry_week'] & (d['roc_5'] < -5.0) & (d['vol_ratio'] > 1.5) & (d['close'] > d['sma_200'])
    
    # Setup C: RV Squeeze Expansion (RV_10 < 0.5 * RV_60, then close crosses above 10 EMA with vol > 1.5x)
    d['rv_squeeze_expansion'] = (d['rv_ratio'].shift(1) < 0.6) & (d['close'] > d['ema_10']) & (d['close'].shift(1) <= d['ema_10'].shift(1)) & (d['vol_ratio'] > 1.5) & (d['close'] > d['sma_200'])
    
    # Setup D: 3-Day Consecutive Panic Drop with Volume Spike in F&O Leaders
    d['fo_3day_panic'] = d['down_3d'] & (d['roc_5'] < -6.0) & (d['vol_ratio'] > 1.8) & (d['close'] > d['sma_200'])
    
    # Setup E: F&O Dip to 50 SMA in Top Momentum Leaders (60d momentum > 20%, low <= sma_50 <= high, close > open)
    d['fo_50sma_bounce'] = (d['momentum_60d'] > 15.0) & (d['low'] <= d['sma_50']) & (d['close'] >= d['sma_50']) & (d['close'] > d['open']) & (d['sma_50'] > d['sma_200'])

    d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'rv_ratio', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Processed {len(processed)} F&O stocks with derivatives features.")

def test_derivatives_strategy(name, signal_fn, horizon=7):
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

test_derivatives_strategy("5. Post-Expiry Oversold Bounce (New Series)", lambda d: d['post_expiry_oversold'], horizon=7)
test_derivatives_strategy("6. Expiry Week Capitulation", lambda d: d['expiry_week_capitulation'], horizon=7)
test_derivatives_strategy("7. Realized Volatility Squeeze Expansion", lambda d: d['rv_squeeze_expansion'], horizon=7)
test_derivatives_strategy("8. F&O 3-Day Panic Drop with Volume Spike", lambda d: d['fo_3day_panic'], horizon=7)
test_derivatives_strategy("9. F&O 50-SMA Bounce in Momentum Leaders", lambda d: d['fo_50sma_bounce'], horizon=7)
