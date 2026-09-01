"""Full feature scan under the v2 protocol (search half / hold-out half / hold-out period)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from lab import build_flat, dayt, IS_END, FWD_START

flat = build_flat()
ms = flat[flat["mid_small"]].copy()
print(f"mid/small rows {len(ms)}, names {ms.ticker.nunique()}, dates {ms.date.nunique()}")

FEATS = [c for c in ms.columns if c not in
         ("date", "ticker", "half", "liq", "mid_small", "open", "high", "low", "close", "volume",
          "fwd6", "fwd8", "fwd10", "fwd6_dm", "fwd8_dm", "fwd10_dm", "turnover", "turn20",
          "vol50", "low20", "high20", "high10", "sma_20", "sma_50", "sma_200", "ema_10", "atr",
          "macd", "macd_signal", "amihud", "turnover_60d")]

HDR = f"{'feature':22s} {'dec':4s} | {'SEARCH(A,IS)':>22s} | {'VALID-U(B,IS)':>22s} | {'VALID-T(fwd)':>22s}"
print(HDR)
print("-" * len(HDR))

rows = []
for f in sorted(FEATS):
    sub = ms.dropna(subset=[f])
    if len(sub) < 20000:
        continue
    q = sub.groupby("date")[f].transform(
        lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if s.notna().sum() >= 10 else np.nan)
    for dec, tag in ((0, "D1"), (9, "D10")):
        sel = sub[q == dec]
        out = {}
        for name, s2 in (("S", sel[(sel.half == "A") & (sel.date <= IS_END)]),
                         ("U", sel[(sel.half == "B") & (sel.date <= IS_END)]),
                         ("T", sel[sel.date >= FWD_START])):
            out[name] = dayt(s2)
        line = (f"{f:22s} {tag:4s} | " +
                " | ".join(f"{out[k][0]:+7.3f}%  t{out[k][1]:+6.2f}" for k in "SUT"))
        # flag: same sign and t>=2 in search AND hold-out universe AND forward
        ts = [out[k][1] for k in "SUT"]
        ok = (all(np.isfinite(t) for t in ts) and
              (all(t >= 1.5 for t in ts) or all(t <= -1.5 for t in ts)))
        print(line + ("   <== CONSISTENT" if ok else ""))
        rows.append((f, tag, *ts, ok))

print("\n=== consistent across all three (|t| >= 1.5, same sign) ===")
for r in rows:
    if r[-1]:
        print(f"  {r[0]:22s} {r[1]:4s}  t: S{r[2]:+.2f} U{r[3]:+.2f} T{r[4]:+.2f}")
