"""Fetch the full liquid NSE universe, 10 years, in batches.

Why: every candidate so far has been breadth-starved. With 443 names the top decile yields ~2
non-overlapping entries per day, so each day's strategy mean - the quantity the paired test works
on - is an average of two stocks and is mostly noise. The fix is more names per day, which is
statistical power, not parameter tuning: the rules do not change.

Keeps only names that clear the repo's validated liquidity floor (60d median turnover >= 25 cr)
on at least 200 sessions, so the cost wall in REJECTED.md is respected up front.
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
import yfinance as yf
from data_loader import add_features

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "cache", "nse_full_10y.pkl")
MIN_TURNOVER = 25e7
MIN_LIQ_BARS = 200
BATCH = 60


def symbols():
    df = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "EQUITY_L.csv"))
    df.columns = [c.strip() for c in df.columns]
    eq = df[df["SERIES"].astype(str).str.strip() == "EQ"]
    return sorted(f"{s.strip()}.NS" for s in eq["SYMBOL"].astype(str))


def main():
    syms = symbols()
    print(f"{len(syms)} EQ symbols", flush=True)
    panel, kept, seen = {}, 0, 0
    t0 = time.time()
    for i in range(0, len(syms), BATCH):
        chunk = syms[i:i + BATCH]
        try:
            raw = yf.download(chunk, period="10y", interval="1d", auto_adjust=True,
                              progress=False, group_by="ticker", threads=True)
        except Exception as e:
            print(f"  batch {i} failed: {e}", flush=True)
            continue
        for t in chunk:
            seen += 1
            try:
                sub = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                sub = sub.dropna(how="all")
                if sub is None or len(sub) < 400:
                    continue
                d = pd.DataFrame({
                    "date": pd.to_datetime(sub.index),
                    "open": sub["Open"].values, "high": sub["High"].values,
                    "low": sub["Low"].values, "close": sub["Close"].values,
                    "volume": sub["Volume"].values,
                }).dropna()
                if len(d) < 400:
                    continue
                d = add_features(d)
                if (d["turnover_60d"] >= MIN_TURNOVER).sum() < MIN_LIQ_BARS:
                    continue
                panel[t] = d
                kept += 1
            except Exception:
                continue
        print(f"  {seen}/{len(syms)} scanned, {kept} liquid kept, {time.time()-t0:.0f}s", flush=True)

    pickle.dump({"__meta__": {"source": "NSE EQUITY_L", "period": "10y"}, "data": panel},
                open(OUT, "wb"))
    print(f"saved {len(panel)} names to {OUT}", flush=True)


if __name__ == "__main__":
    main()
