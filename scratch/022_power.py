"""Is '1 of 5 folds clears 2.0' evidence AGAINST strategy 022, or just what low per-fold power
looks like? Answered two ways, both from the real trade list - no simulation of made-up returns.

1. Analytic expectation: if the effect is homogeneous, per-fold z ~ pooled_z / sqrt(n_folds).
   Compare the observed fold z's against that, and against the count of folds you would EXPECT to
   clear 2.0.
2. Randomisation: shuffle the day-level paired differences across time (destroying any real
   period structure but preserving the marginal distribution), re-cut into 5 folds, and ask how
   often a HOMOGENEOUS effect of exactly this size produces as few as 1 fold clearing 2.0.
   If 1/5 is common under homogeneity, the fold criterion carries no information about stability.
3. The genuine alternative it must be separated from: a real regime break. Tested by comparing the
   observed spread of fold z's against the spread the shuffle produces (a variance ratio).
"""
import sys, os, importlib, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategies"))
import numpy as np, pandas as pd

m = importlib.import_module("022_risk_adjusted_12_month_momentum_swing_in_mid_small_caps")

panel = m.prepare(m.load("master_10y"))
full = m.slice_panel(panel)
print(f"universe {len(full)} liquid mid/small", flush=True)

strat, cf = m.run_set(full)
ctrl = cf(0)

s = pd.Series([t["net_pct"] for t in strat], index=[t["entry_date"] for t in strat]).groupby(level=0).mean()
c = pd.Series([t["net_pct"] for t in ctrl], index=[t["entry_date"] for t in ctrl]).groupby(level=0).mean()
paired = (s - c).dropna().sort_index()
n = len(paired)
z_pooled = paired.mean() / (paired.std(ddof=1) / np.sqrt(n))
print(f"paired days {n}, day_edge {paired.mean():+.4f}%, pooled z {z_pooled:+.2f}", flush=True)

K = 5
def fold_zs(series):
    out = []
    for chunk in np.array_split(np.asarray(series), K):
        if len(chunk) > 5 and chunk.std(ddof=1) > 0:
            out.append(chunk.mean() / (chunk.std(ddof=1) / np.sqrt(len(chunk))))
    return np.array(out)

obs = fold_zs(paired.values)
print(f"\nobserved fold z: {np.round(obs,2)}  (mean {obs.mean():.2f}, sd {obs.std(ddof=1):.2f})")
print(f"analytic expectation per fold if homogeneous: {z_pooled/np.sqrt(K):.2f}")

rng = np.random.default_rng(0)
vals = paired.values
n_clear, spreads, means = [], [], []
for _ in range(4000):
    sh = rng.permutation(vals)                 # homogeneous by construction
    fz = fold_zs(sh)
    n_clear.append((fz >= 2.0).sum())
    spreads.append(fz.std(ddof=1))
    means.append(fz.mean())
n_clear = np.array(n_clear); spreads = np.array(spreads)

print(f"\nunder a HOMOGENEOUS effect of this exact size (4000 shuffles):")
for k in range(6):
    print(f"   folds clearing 2.0 == {k}: {100*(n_clear==k).mean():5.1f}%")
print(f"   P(<= 1 fold clears) = {100*(n_clear<=1).mean():.1f}%   <- observed was 1")
print(f"   mean folds clearing = {n_clear.mean():.2f}")

print(f"\nfold-z spread: observed {obs.std(ddof=1):.2f} vs homogeneous {spreads.mean():.2f} "
      f"(p={100*(spreads>=obs.std(ddof=1)).mean():.1f}% of shuffles are at least as spread out)")
print("   -> a real regime break would show observed spread ABOVE the homogeneous distribution")

# the honest counter-check: is the WEAK period genuinely different, or noise?
print("\n=== per-fold detail with confidence intervals ===")
for i, chunk in enumerate([paired.iloc[a[0]:a[-1]+1] for a in np.array_split(np.arange(len(paired)), K)]):
    mu = chunk.mean(); se = chunk.std(ddof=1)/np.sqrt(len(chunk))
    print(f"  fold {i+1} {chunk.index[0].date()}..{chunk.index[-1].date()}  "
          f"edge {mu:+.3f}% +/- {1.96*se:.3f}  z {mu/se:+.2f}  days {len(chunk)}")

print("\n=== per calendar year, actual traded paired series ===")
for y, g in paired.groupby(paired.index.year):
    if len(g) < 30:
        print(f"  {y}: {len(g)} days - too few"); continue
    se = g.std(ddof=1)/np.sqrt(len(g))
    print(f"  {y}: edge {g.mean():+.3f}%  z {g.mean()/se:+5.2f}  days {len(g)}")
