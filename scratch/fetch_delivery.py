"""Fetch NSE daily delivery data, 10 years, resumable.

Two NSE sources, because the modern one does not go back far enough:
  * 2019-07 onward : products/content/sec_bhavdata_full_DDMMYYYY.csv
        -> DELIV_QTY, DELIV_PER, NO_OF_TRADES, TTL_TRD_QNTY, TURNOVER_LACS
  * before that    : archives/equities/mto/MTO_DDMMYYYY.DAT
        -> deliverable quantity and % only (no trade counts)

Why this data: DELIV_PER is the share of the day's volume actually taken to demat rather than
squared off intraday, and TURNOVER/NO_OF_TRADES is the average ticket size. Both describe WHO
traded, which price and volume cannot, and neither exists in yfinance. Every candidate in this
session topped out because daily OHLCV alone supports only ~0.4%/8-session cross-sectional edges.

Each session is cached as its own pickle in cache/delivery_raw/, so an interrupted run resumes.
A day NSE genuinely has no file for (holiday) is cached as an empty list; a day that FAILED for
any other reason is not cached, so it gets retried on the next run.
"""
import os, io, csv, time, pickle
import urllib.request, urllib.error
import datetime as dt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "cache", "delivery_raw")
FULL_URL = "https://archives.nseindia.com/products/content/sec_bhavdata_full_{}.csv"
MTO_URL = "https://archives.nseindia.com/archives/equities/mto/MTO_{}.DAT"
HDRS = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*"}
FULL_FROM = dt.date(2019, 7, 1)          # probed: works from mid-2019, 404 before


def _get(url):
    req = urllib.request.Request(url, headers=HDRS)
    try:
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return None
        raise


def parse_full(txt):
    out = []
    for r in csv.DictReader(io.StringIO(txt)):
        r = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
        if r.get("SERIES") != "EQ":
            continue
        out.append({
            "symbol": r["SYMBOL"], "close": r.get("CLOSE_PRICE"),
            "volume": r.get("TTL_TRD_QNTY"), "turnover_lacs": r.get("TURNOVER_LACS"),
            "trades": r.get("NO_OF_TRADES"), "deliv_qty": r.get("DELIV_QTY"),
            "deliv_pct": r.get("DELIV_PER"),
        })
    return out


def parse_mto(txt):
    out = []
    for line in txt.splitlines():
        p = [x.strip() for x in line.split(",")]
        # record type 20 = a security row: 20,srno,SYMBOL,SERIES,traded,delivered,pct
        if len(p) < 7 or p[0] != "20" or p[3] != "EQ":
            continue
        out.append({
            "symbol": p[2], "close": None, "volume": p[4], "turnover_lacs": None,
            "trades": None, "deliv_qty": p[5], "deliv_pct": p[6],
        })
    return out


def main(years=10):
    os.makedirs(OUT_DIR, exist_ok=True)
    end = dt.date(2026, 8, 21)
    day = end - dt.timedelta(days=365 * years + 10)
    got = miss = cached = fails = 0
    t0 = time.time()
    while day <= end:
        if day.weekday() >= 5:
            day += dt.timedelta(days=1)
            continue
        path = os.path.join(OUT_DIR, day.strftime("%Y%m%d") + ".pkl")
        if os.path.exists(path):
            cached += 1
            day += dt.timedelta(days=1)
            continue
        ds = day.strftime("%d%m%Y")
        try:
            if day >= FULL_FROM:
                txt = _get(FULL_URL.format(ds))
                rows = parse_full(txt) if txt else None
            else:
                txt = _get(MTO_URL.format(ds))
                rows = parse_mto(txt) if txt else None
        except Exception:
            fails += 1
            time.sleep(2.0)
            day += dt.timedelta(days=1)
            continue
        if rows is None:
            miss += 1
            pickle.dump([], open(path, "wb"))       # genuine non-trading day
        else:
            got += 1
            pickle.dump(rows, open(path, "wb"))
        time.sleep(0.10)
        if (got + miss) % 200 == 0:
            print(f"  {day} | sessions {got}, non-trading {miss}, cached {cached}, "
                  f"fails {fails}, {time.time()-t0:.0f}s", flush=True)
        day += dt.timedelta(days=1)
    print(f"done: {got} sessions, {miss} non-trading, {cached} pre-cached, {fails} failures, "
          f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
