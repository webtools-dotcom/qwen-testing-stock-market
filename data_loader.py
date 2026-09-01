"""Data + features. One correct place to build a price panel, so every strategy tests on the
same bars with the same indicators — and so Gemini never hand-rolls RSI/ATR wrong.

Data source: yfinance (same as the sister project). Free, no key, good enough for daily-bar
research. Swap get_panel() if you move to a paid feed later; nothing else needs to change.

RSI/ATR use the `ta` library with Wilder's defaults (14) — identical to the sister project, so
results are directly comparable to what's already in REJECTED.md.

Run `python data_loader.py` to fetch a tiny 3-stock panel and confirm the pipeline works.
"""

import os
import pickle
import numpy as np
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")


def add_features(df):
    """Add rsi, atr, atr_pct, sma/ema, momentum, turnover_60d. Expects columns:
    date, open, high, low, close, volume. Returns the frame with NaNs left in the warmup
    period (drop them in your strategy, don't forward-fill — that fabricates history)."""
    import ta
    df = df.sort_values('date').reset_index(drop=True)
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    atr = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14)
    df['atr'] = atr.average_true_range()
    df['atr_pct'] = df['atr'] / df['close'] * 100
    df['sma_20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
    df['sma_50'] = ta.trend.SMAIndicator(close=df['close'], window=50).sma_indicator()
    df['sma_200'] = ta.trend.SMAIndicator(close=df['close'], window=200).sma_indicator()
    df['ema_10'] = ta.trend.EMAIndicator(close=df['close'], window=10).ema_indicator()
    macd = ta.trend.MACD(close=df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['momentum_60d'] = df['close'].pct_change(60) * 100
    df['change_252d'] = df['close'].pct_change(252) * 100
    df['distance_from_high_50'] = df['close'] / df['close'].rolling(50).max() - 1
    df['volume_change'] = df['volume'].pct_change(20)
    df['turnover'] = df['close'] * df['volume']
    df['turnover_60d'] = df['turnover'].rolling(60).median()   # median, not mean — robust to spikes
    return df


def get_panel(tickers, period="5y", cache_name=None, force=False):
    """Download daily bars for `tickers`, add features, return {ticker: DataFrame}.

    Caches to cache/<cache_name>.pkl so you fetch once and backtest many times. Pass force=True
    to re-download. Use ".NS" suffixes for NSE (e.g. "RELIANCE.NS"), ".BO" for BSE.

    IMPORTANT on look-ahead: yfinance gives daily OHLC. Your entry must be a bar the signal
    could actually be known at — for an event/close signal, enter at the NEXT bar's open, never
    the same close. The engine's exit logic already enforces this for RSI-recovery exits.
    """
    import yfinance as yf
    fingerprint = {'tickers': sorted(tickers), 'period': period}
    path = os.path.join(CACHE_DIR, f"{cache_name}.pkl") if cache_name else None
    if path and os.path.exists(path) and not force:
        with open(path, 'rb') as fh:
            obj = pickle.load(fh)
        # New format carries a fingerprint; re-download if the universe/period changed (or if the
        # cache is a legacy raw dict with no fingerprint) so you never silently get stale data.
        if isinstance(obj, dict) and obj.get('__meta__') == fingerprint:
            return obj['data']
        print(f"  cache '{cache_name}' is stale or legacy (universe/period changed) — re-downloading")

    panel = {}
    for t in tickers:
        try:
            raw = yf.download(t, period=period, interval="1d", auto_adjust=True, progress=False)
            if raw is None or len(raw) < 250:
                print(f"  skip {t}: only {0 if raw is None else len(raw)} bars")
                continue
            if isinstance(raw.columns, pd.MultiIndex):     # yfinance returns MultiIndex for 1 ticker sometimes
                raw.columns = raw.columns.get_level_values(0)
            df = pd.DataFrame({
                'date': pd.to_datetime(raw.index),
                'open': raw['Open'].values, 'high': raw['High'].values,
                'low': raw['Low'].values, 'close': raw['Close'].values,
                'volume': raw['Volume'].values,
            })
            panel[t] = add_features(df)
        except Exception as e:
            print(f"  skip {t}: {e}")

    if cache_name and panel:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path, 'wb') as fh:
            pickle.dump({'__meta__': fingerprint, 'data': panel}, fh)
    return panel


# A small default universe for smoke tests. For real research, load a proper NSE list
# (Nifty 500 constituents, or the sister project's 748-name watchlist).
SMOKE_UNIVERSE = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]


def demo():
    """Fetch a 3-stock panel and assert the pipeline produces usable RSI/ATR."""
    panel = get_panel(SMOKE_UNIVERSE, period="2y", cache_name="_smoke", force=True)
    assert len(panel) >= 1, "no stocks fetched — check network / yfinance"
    df = next(iter(panel.values()))
    assert {'rsi', 'atr', 'close', 'turnover_60d'}.issubset(df.columns)
    assert df['rsi'].dropna().between(0, 100).all(), "RSI out of range — feature bug"
    # ATR can legitimately be 0 on a flat/halted bar (high==low); the engine skips those. Just
    # require it's non-negative and mostly positive, not strictly positive everywhere.
    atr = df['atr'].dropna()
    assert (atr >= 0).all() and (atr > 0).mean() > 0.9, "ATR pipeline looks broken"
    print(f"data_loader.py self-check passed ({len(panel)} stocks, {len(df)} bars each)")


if __name__ == "__main__":
    demo()
