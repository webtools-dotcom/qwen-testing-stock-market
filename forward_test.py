"""Forward test + live scanner for strategy 024 (monthly-hold risk-adjusted 12-month momentum).

This exists because 024 passed all nine of its pre-registered kill criteria but is the winner of
the largest search in this repo, and METHODOLOGY §9 says the only check a large search cannot fake
is time it has not seen. Every hold-out used so far was carved out of data the search could see.
So: record the picks now, score them when they mature, and let reality vote.

    python forward_test.py scan      # today's picks -> appended to forward_log.csv
    python forward_test.py score     # score matured picks against the backtest claim

The claim being tested, from strategies/024_*.md:
    day-clustered paired edge  +0.984% per 21-session holding period vs a random-entry control
    portfolio CAGR             ~+19% with a ~-42% max drawdown

Deliberately dumb: one CSV, no database, no scheduler. Run it weekly.
"""

import os
import sys
import pickle
import datetime as dt

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE, "forward_log.csv")
HOLD = 21
TOP_PCT = 0.90
MIN_TURNOVER = 25e7
N_PICKS = 20

NIFTY_50 = {f"{t}.NS" for t in """RELIANCE TCS INFY HDFCBANK SBIN AXISBANK LT ITC HINDUNILVR MARUTI
TATASTEEL JSWSTEEL CIPLA DRREDDY WIPRO TECHM HCLTECH BAJFINANCE ASIANPAINT ULTRACEMCO GRASIM
POWERGRID NTPC ONGC ADANIPORTS TITAN NESTLEIND BRITANNIA DIVISLAB EICHERMOT BAJAJ-AUTO BAJAJFINSV
BHARTIARTL BPCL HEROMOTOCO HINDALCO INDUSINDBK KOTAKBANK M&M SBILIFE SHRIRAMFIN TRENT APOLLOHOSP
COALINDIA ICICIBANK SUNPHARMA TATAMOTORS LTIM ADANIENT TATACONSUM HDFCLIFE JIOFIN""".split()}


def universe():
    """The names the strategy was validated on."""
    obj = pickle.load(open(os.path.join(BASE, "cache", "master_10y.pkl"), "rb"))
    return sorted(obj["data"].keys())


def fresh_panel(tickers, period="2y"):
    """Re-download recent bars. 2y covers the 252-session lookback with room to spare."""
    from data_loader import get_panel
    return get_panel(tickers, period=period, cache_name="forward_scan", force=True)


def score_frame(panel):
    """Cross-sectional score on the most recent common date. Same rules as strategies/024."""
    rows = []
    for t, d in panel.items():
        if t in NIFTY_50 or len(d) < 260:
            continue
        d = d.dropna(subset=["close"]).reset_index(drop=True)
        r = d["close"].pct_change()
        vol60 = r.rolling(60).std().iloc[-1] * 100
        chg252 = (d["close"].iloc[-1] / d["close"].iloc[-253] - 1) * 100 if len(d) > 253 else np.nan
        turn = d["turnover_60d"].iloc[-1]
        if not np.isfinite(vol60) or vol60 <= 0 or not np.isfinite(chg252):
            continue
        rows.append({"ticker": t, "date": d["date"].iloc[-1], "close": d["close"].iloc[-1],
                     "score": chg252 / vol60, "turnover_60d": turn,
                     "liquid": bool(np.isfinite(turn) and turn >= MIN_TURNOVER)})
    df = pd.DataFrame(rows)
    elig = df[df["liquid"]].copy()
    elig["rank"] = elig["score"].rank(pct=True)
    return elig.sort_values("score", ascending=False)


def scan():
    tk = universe()
    print(f"downloading {len(tk)} names...", flush=True)
    panel = fresh_panel(tk)
    elig = score_frame(panel)
    if elig.empty:
        print("no eligible names - check the data download")
        return
    asof = elig["date"].max()
    picks = elig[elig["rank"] >= TOP_PCT].head(N_PICKS)
    print(f"\nas of {asof.date()}: {len(elig)} liquid mid/small names, "
          f"{(elig['rank'] >= TOP_PCT).sum()} in the top decile\n")
    print(f"{'ticker':16s} {'close':>10s} {'score':>8s} {'turnover_cr':>12s}")
    for _, r in picks.iterrows():
        print(f"{r.ticker:16s} {r.close:10.2f} {r.score:8.2f} {r.turnover_60d/1e7:12.1f}")

    out = picks[["ticker", "close", "score"]].copy()
    out.insert(0, "signal_date", asof.date())
    out["planned_exit_sessions"] = HOLD
    out["exit_after"] = (asof + pd.tseries.offsets.BDay(HOLD)).date()
    out["status"] = "open"
    header = not os.path.exists(LOG)
    out.to_csv(LOG, mode="a", header=header, index=False)
    print(f"\n{len(out)} picks appended to {LOG}")
    print("Re-run `python forward_test.py score` once these mature.")


def score():
    if not os.path.exists(LOG):
        print("no forward_log.csv yet - run `python forward_test.py scan` first")
        return
    log = pd.read_csv(LOG, parse_dates=["signal_date", "exit_after"])
    open_rows = log[log["status"] == "open"]
    if open_rows.empty:
        print("nothing open to score")
        return
    due = open_rows[open_rows["exit_after"] <= pd.Timestamp(dt.date.today())]
    print(f"{len(open_rows)} open picks, {len(due)} matured", flush=True)
    if due.empty:
        nxt = open_rows["exit_after"].min()
        print(f"next matures {nxt.date()}")
        return

    from data_loader import get_panel
    panel = get_panel(sorted(due["ticker"].unique()), period="1y",
                      cache_name="forward_score", force=True)
    res = []
    for i, r in due.iterrows():
        d = panel.get(r.ticker)
        if d is None:
            continue
        after = d[d["date"] > r.signal_date]
        if len(after) < HOLD:
            continue
        exit_px = after["close"].iloc[HOLD - 1]
        gross = (exit_px - r.close) / r.close * 100
        res.append({"idx": i, "ticker": r.ticker, "signal_date": r.signal_date,
                    "gross_pct": gross, "net_pct": gross - 0.50})
    if not res:
        print("matured picks found but not enough bars yet")
        return
    rr = pd.DataFrame(res)
    print(f"\n{'ticker':16s} {'signal':>12s} {'gross%':>8s} {'net%':>8s}")
    for _, x in rr.iterrows():
        print(f"{x.ticker:16s} {str(x.signal_date.date()):>12s} {x.gross_pct:8.2f} {x.net_pct:8.2f}")
    print(f"\nmean net {rr.net_pct.mean():+.3f}%  median {rr.net_pct.median():+.3f}%  "
          f"win rate {100*(rr.net_pct > 0).mean():.0f}%  n={len(rr)}")
    print("\nBACKTEST CLAIM to beat: +0.984% per 21 sessions ABOVE a random-entry control.")
    print("A raw mean above zero is NOT the test - the control matters, and n must be large")
    print("enough to say anything. Treat fewer than ~10 independent signal dates as noise.")

    log.loc[rr["idx"], "status"] = "scored"
    log.to_csv(LOG, index=False)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    {"scan": scan, "score": score}.get(cmd, scan)()
