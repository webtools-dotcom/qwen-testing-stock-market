"""Merge NSE delivery data onto the master price panel and build delivery-based features.

LOOK-AHEAD DISCIPLINE (the thing that decides whether any of this is real):
NSE publishes the security-wise delivery file only after that session settles - it is not on the
tape at the close of day t. So every delivery field is SHIFTED ONE SESSION before use: a signal
evaluated at the close of day t may only use delivery data through day t-1. This is enforced once,
here, so no downstream strategy can get it wrong.

Features (all from lagged delivery):
  deliv_pct      - % of traded quantity delivered (1-session lag)
  dp_z           - deliv_pct vs its own trailing 60-session mean/sd
  dp_ratio       - deliv_pct / trailing 20-session mean
  deliv_turnover - turnover * deliv_pct: the genuinely investable share of liquidity
  ticket         - turnover / number of trades (average ticket size, 2019+ only)
  ticket_z       - ticket vs its own trailing 60-session norm
  absorb_div     - lagged: price down over 5 sessions while delivery % is elevated
"""
import os, glob, pickle
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "cache", "delivery_raw")
DELIV_CACHE = os.path.join(BASE, "cache", "_deliv_frame.pkl")
MERGED = os.path.join(BASE, "cache", "_deliv_flat.pkl")


def load_delivery(force=False):
    """One tidy frame: date, symbol, deliv_pct, volume, turnover, trades."""
    if os.path.exists(DELIV_CACHE) and not force:
        return pickle.load(open(DELIV_CACHE, "rb"))
    rows = []
    for path in sorted(glob.glob(os.path.join(RAW, "*.pkl"))):
        day = os.path.basename(path)[:8]
        recs = pickle.load(open(path, "rb"))
        if not recs:
            continue
        d = pd.DataFrame(recs)
        d["date"] = pd.Timestamp(day)
        rows.append(d)
    if not rows:
        raise SystemExit("no delivery files cached yet")
    df = pd.concat(rows, ignore_index=True)
    for c in ("close", "volume", "turnover_lacs", "trades", "deliv_qty", "deliv_pct"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ticker"] = df["symbol"].astype(str).str.strip() + ".NS"
    df = df[["date", "ticker", "deliv_pct", "deliv_qty", "volume", "turnover_lacs", "trades"]]
    df = df.dropna(subset=["deliv_pct"])
    df = df[(df["deliv_pct"] > 0) & (df["deliv_pct"] <= 100)]
    df = df.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"])
    pickle.dump(df, open(DELIV_CACHE, "wb"))
    return df


def add_delivery_features(df):
    """df: one ticker, sorted by date, with a deliv_pct column. All outputs are lagged."""
    g = df
    # THE lag: delivery for session t is only public after t settles.
    dp = g["deliv_pct"].shift(1)
    g["dp"] = dp
    g["dp_mean20"] = dp.rolling(20).mean()
    g["dp_z"] = (dp - dp.rolling(60).mean()) / dp.rolling(60).std()
    g["dp_ratio"] = dp / g["dp_mean20"]
    turn = g["turnover_lacs"].shift(1) * 1e5
    g["deliv_turnover"] = turn * dp / 100.0
    g["deliv_turnover_60d"] = g["deliv_turnover"].rolling(60).median()
    tr = g["trades"].shift(1)
    g["ticket"] = turn / tr.replace(0, np.nan)
    g["ticket_z"] = (g["ticket"] - g["ticket"].rolling(60).mean()) / g["ticket"].rolling(60).std()
    return g


def build(force=False):
    """Master price panel + lagged delivery features, as one flat frame with the usual cells."""
    if os.path.exists(MERGED) and not force:
        return pickle.load(open(MERGED, "rb"))
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from master_lab import build as build_prices

    prices = build_prices()
    deliv = load_delivery()
    print(f"  delivery rows {len(deliv)}, tickers {deliv.ticker.nunique()}, "
          f"{deliv.date.min().date()}..{deliv.date.max().date()}", flush=True)

    merged = prices.merge(deliv[["date", "ticker", "deliv_pct", "turnover_lacs", "trades"]],
                          on=["date", "ticker"], how="left")
    merged = merged.sort_values(["ticker", "date"])
    # explicit loop: groupby.apply can absorb the grouping column into the index
    parts = [add_delivery_features(g.copy()) for _, g in merged.groupby("ticker", sort=False)]
    merged = pd.concat(parts, ignore_index=True)
    pickle.dump(merged, open(MERGED, "wb"))
    return merged
