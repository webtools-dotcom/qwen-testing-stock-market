"""Systematic pair scan: every feature decile x every conditioning tercile, scored for
consistency across SEARCH half / hold-out half of NAMES / hold-out forward PERIOD.

A combo only survives if all three t-stats have the same sign and |t| >= 2. With ~2000 combos
some pass by luck, so survivors are ranked by min(|t|) and only the top few go to the engine,
where the hold-out half and forward window are re-checked as formal kill criteria.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from lab import build_flat, dayt, IS_END, FWD_START

flat = build_flat()
ms = flat[flat["mid_small"]].copy()

BASE_FEATS = ["ret_ex20_120", "ret_ex5_20", "ret120", "ret20", "ret5", "resid5", "resid20",
              "rsi", "atr_pct", "amihud_z", "turnover_z", "vol_ratio1", "vol_ratio3", "obv_ch20",
              "rng_pos5", "dist_high20", "dist_high250", "bb_bw_rank", "bb_pos", "close_sma20",
              "close_sma50", "close_sma200", "sma20_slope", "sma50_slope", "skew60", "kurt60",
              "maxret20", "corr_mkt", "idio_vol", "vol_ratio_2060", "up_days20", "dn_streak",
              "intraday20", "oc_gap20", "sharpe60", "dev_avwap", "drop_atr5", "turn_ratio20"]

def q(df, col, n):
    return df.groupby("date")[col].transform(
        lambda s: pd.qcut(s.rank(method="first"), n, labels=False) if s.notna().sum() >= n else np.nan)

# precompute decile + tercile labels once
lab = pd.DataFrame(index=ms.index)
for f in BASE_FEATS:
    if ms[f].notna().sum() < 20000:
        continue
    lab[f + "_d"] = q(ms, f, 10)
    lab[f + "_t"] = q(ms, f, 3)
ms = pd.concat([ms, lab], axis=1)
feats = [f for f in BASE_FEATS if f + "_d" in ms.columns]
print(f"{len(feats)} usable features -> {len(feats)*(len(feats)-1)*2*3//1} combos", flush=True)

S = (ms.half == "A") & (ms.date <= IS_END)
U = (ms.half == "B") & (ms.date <= IS_END)
T = ms.date >= FWD_START

results = []
for i, f in enumerate(feats):
    for dec, tag in ((9, "D10"), (0, "D1")):
        base = ms[f + "_d"] == dec
        if base.sum() < 3000:
            continue
        for g in feats:
            if g == f:
                continue
            for tq in (0, 1, 2):
                sel = base & (ms[g + "_t"] == tq)
                if sel.sum() < 2500:
                    continue
                ts, ms_ = [], []
                for mask in (S, U, T):
                    mm, tt, nn = dayt(ms[sel & mask])
                    if not np.isfinite(tt) or nn < 100:
                        ts = None
                        break
                    ts.append(tt); ms_.append(mm)
                if ts is None:
                    continue
                if (all(t >= 2.0 for t in ts) or all(t <= -2.0 for t in ts)):
                    results.append((min(abs(t) for t in ts), f, tag, g, tq, ts, ms_, int(sel.sum())))
    print(f"  ..{i+1}/{len(feats)} scanned, {len(results)} survivors", flush=True)

results.sort(reverse=True)
print(f"\n=== {len(results)} combos consistent at |t|>=2 in all three sets ===")
for r in results[:40]:
    mn, f, tag, g, tq, ts, mms, n = r
    print(f"  min|t|={mn:4.2f}  {f:16s}{tag:4s} x {g:14s}T{tq}  n={n:6d}  "
          f"S {mms[0]:+.3f}%/t{ts[0]:+5.2f}  U {mms[1]:+.3f}%/t{ts[1]:+5.2f}  T {mms[2]:+.3f}%/t{ts[2]:+5.2f}")
import pickle
pickle.dump(results, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pairscan.pkl"), "wb"))
