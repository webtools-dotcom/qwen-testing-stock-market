"""Three attacks on 024's tool test: cost breakeven, warm-up distortion, and a REAL investable
benchmark (Nifty Midcap 50) instead of a cost-free daily-rebalanced equal-weight construction."""
import sys, os, importlib, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategies"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
m = importlib.import_module("022_risk_adjusted_12_month_momentum_swing_in_mid_small_caps")
pf = importlib.import_module("022_portfolio")

HOLD = 21
panel = m.prepare(m.load("master_10y"))
full = m.slice_panel(panel)
df = pf.build_frame(full)

def cagr(eq, lo=None):
    if lo is not None:
        eq = eq[eq.index >= lo]
        eq = eq / eq.iloc[0]
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return eq.iloc[-1] ** (1/yrs) - 1

bench = pf.run_portfolio(df, "benchmark")
print("=== 1. cost breakeven (strategy CAGR vs cost-free buy-and-hold) ===", flush=True)
b = cagr(bench)
print(f"   buy-and-hold (cost-free, daily-rebalanced): {b*100:+.2f}%", flush=True)
for cm in (1.0, 1.2, 1.4, 1.6, 2.0):
    e = pf.run_portfolio(df, "strategy", hold=HOLD, cost_mult=cm)
    c = cagr(e)
    print(f"   costs x{cm} ({0.50*cm:.2f}% round trip): {c*100:+.2f}%  "
          f"{'BEATS' if c > b else 'loses to'} buy-and-hold", flush=True)

print("\n=== 2. warm-up: the signal needs 252 sessions, so 2016-17 is not a fair sample ===",
      flush=True)
eq = pf.run_portfolio(df, "strategy", hold=HOLD)
for lo in (None, "2018-01-01", "2019-01-01"):
    lo_ts = pd.Timestamp(lo) if lo else None
    print(f"   from {lo or 'start'}: strategy {cagr(eq, lo_ts)*100:+.2f}%  "
          f"buy-and-hold {cagr(bench, lo_ts)*100:+.2f}%", flush=True)

print("\n=== 3. a REAL investable benchmark: Nifty Midcap 50 total price index ===", flush=True)
mac = pickle.load(open(os.path.join(m.BASE, "cache", "macro.pkl"), "rb"))
idx = mac.get("niftymid")
if idx is not None:
    idx = idx[(idx.index >= eq.index[0]) & (idx.index <= eq.index[-1])].dropna()
    idx = idx / idx.iloc[0]
    print(f"   Nifty Midcap 50: {cagr(idx)*100:+.2f}%  maxDD {(idx/idx.cummax()-1).min()*100:.1f}%",
          flush=True)
    print(f"   strategy       : {cagr(eq)*100:+.2f}%  maxDD {(eq/eq.cummax()-1).min()*100:.1f}%",
          flush=True)
    for lo in ("2018-01-01", "2019-01-01"):
        lo_ts = pd.Timestamp(lo)
        print(f"   from {lo}: strategy {cagr(eq, lo_ts)*100:+.2f}%  "
              f"midcap50 {cagr(idx[idx.index>=lo_ts]/idx[idx.index>=lo_ts].iloc[0])*100:+.2f}%",
              flush=True)

print("\n=== 4. how concentrated is the outperformance? excess by year, sorted ===", flush=True)
ex = []
for y in sorted(set(eq.index.year)):
    a = eq[eq.index.year == y]; bb = bench[bench.index.year == y]
    if len(a) < 20:
        continue
    ex.append((y, (a.iloc[-1]/a.iloc[0]-1) - (bb.iloc[-1]/bb.iloc[0]-1)))
ex_s = sorted(ex, key=lambda x: -x[1])
print("   " + "  ".join(f"{y}:{v*100:+.1f}" for y, v in ex_s), flush=True)
tot = sum(v for _, v in ex)
top2 = sum(v for _, v in ex_s[:2])
print(f"   total excess {tot*100:+.1f}pp; best 2 years {top2*100:+.1f}pp "
      f"({100*top2/tot:.0f}% of it); excess excluding best 2: {(tot-top2)*100:+.1f}pp", flush=True)
