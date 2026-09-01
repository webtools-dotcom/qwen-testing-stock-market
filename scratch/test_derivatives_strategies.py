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

# Load cached 141-stock panel
path = os.path.join(CACHE_DIR, "nifty_research_150_5y.pkl")
with open(path, 'rb') as fh:
    obj = pickle.load(fh)
panel = obj['data']

# Fetch India VIX and Nifty Index daily data
print("Fetching India VIX and Nifty index data...")
vix = yf.download("^INDIAVIX", period="5y", interval="1d", auto_adjust=True, progress=False)
if isinstance(vix.columns, pd.MultiIndex):
    vix.columns = vix.columns.get_level_values(0)
vix_df = pd.DataFrame({'date': pd.to_datetime(vix.index), 'vix_close': vix['Close'].values})
vix_df['vix_roc_5'] = vix_df['vix_close'].pct_change(5) * 100
vix_df['vix_sma_3'] = vix_df['vix_close'].rolling(3).mean()
vix_df['vix_peak_reversal'] = (vix_df['vix_roc_5'].shift(1) > 15.0) & (vix_df['vix_close'] < vix_df['vix_sma_3'])

# List of major liquid NSE F&O stocks
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
    d = d.merge(vix_df, on='date', how='left')
    
    # Calculate Last Thursday of the month (Expiry Day)
    # Monthly expiry in NSE: last Thursday of the month
    d['day_of_week'] = d['date'].dt.dayofweek # Thursday = 3
    d['month'] = d['date'].dt.month
    d['year'] = d['date'].dt.year
    
    # Check if Thursday is the last Thursday in that month
    # A Thursday is last Thursday if day + 7 > days in month
    d['is_thursday'] = d['day_of_week'] == 3
    d['is_friday'] = d['day_of_week'] == 4
    
    # Price and Volume metrics
    d['roc_5'] = d['close'].pct_change(5) * 100
    d['roc_10'] = d['close'].pct_change(10) * 100
    d['roc_15'] = d['close'].pct_change(15) * 100
    d['vol_med_20'] = d['volume'].rolling(20).median()
    d['vol_ratio'] = d['volume'] / d['vol_med_20']
    d['bar_range'] = (d['high'] - d['low']).replace(0, np.nan)
    d['bar_pos'] = (d['close'] - d['low']) / d['bar_range']
    d['daily_ret'] = d['close'].pct_change() * 100
    
    # Short squeeze burst: down over 5d, today up > +2.5% on vol > 2.0x, close near high
    d['short_squeeze_burst'] = (d['roc_5'].shift(1) < -5.0) & (d['daily_ret'] > 2.5) & (d['vol_ratio'] > 2.0) & (d['bar_pos'] > 0.75) & (d['close'] > d['sma_200'])
    
    # VIX spike reversal: VIX dropped after >15% surge, stock is above SMA 200 and oversold
    d['vix_reversal_entry'] = (d['vix_peak_reversal'] == True) & (d['rsi'] < 40) & (d['close'] > d['sma_200'])
    
    # F&O High-Beta Oversold Exhaustion: 5-day RoC < -7%, RSI < 35, Close > SMA 200
    d['fo_oversold_exhaustion'] = (d['roc_5'] < -7.0) & (d['rsi'] < 35) & (d['close'] > d['sma_200'])
    
    # Expiry week oversold dip: Last 5 days of monthly series down > -6%
    d['expiry_dip'] = (d['roc_10'] < -8.0) & (d['close'] > d['sma_200']) & (d['rsi'] < 35)

    d = d.dropna(subset=['rsi', 'atr', 'close', 'sma_200', 'turnover_60d']).reset_index(drop=True)
    if len(d) >= 300:
        processed[ticker] = d

print(f"Processed {len(processed)} F&O liquid stocks.")

def test_derivatives_strategy(name, signal_fn, horizon=7):
    print(f"\n=======================================================")
    print(f"Testing Derivatives Strategy: {name} (Horizon {horizon}d)")
    print(f"=======================================================")
    
    # Single seed run
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
          
    # Multi-seed test (20 seeds) via control factory
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

test_derivatives_strategy("1. Short-Squeeze Volume Thrust in F&O Stocks", lambda d: d['short_squeeze_burst'], horizon=7)
test_derivatives_strategy("2. India VIX Spike Reversal Dip-Buying", lambda d: d['vix_reversal_entry'], horizon=7)
test_derivatives_strategy("3. F&O High-Beta 5-day Oversold Exhaustion", lambda d: d['fo_oversold_exhaustion'], horizon=7)
test_derivatives_strategy("4. F&O 10-day RoC Dip in Trend", lambda d: (d['roc_10'] < -10.0) & (d['close'] > d['sma_200']), horizon=7)
