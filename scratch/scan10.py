import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from lab10 import build, cells, fmt_cells, score, CELLS

flat = build(force=True)
print(f"rows {len(flat)} names {flat.ticker.nunique()} dates {flat.date.nunique()} "
      f"{flat.date.min().date()}..{flat.date.max().date()}", flush=True)
print(flat.groupby(['half','period']).size(), flush=True)
ms = flat[flat["mid_small"]].copy()

SKIP = {"date","ticker","half","period","liq","mid_small","open","high","low","close","volume",
        "fwd6","fwd8","fwd10","fwd6_dm","fwd8_dm","fwd10_dm","turnover","turn20","vol50","low20",
        "high20","high10","sma_20","sma_50","sma_200","ema_10","atr","macd","macd_signal",
        "amihud","turnover_60d"}
FEATS = sorted(c for c in ms.columns if c not in SKIP and ms[c].notna().sum() > 50000)
print(f"{len(FEATS)} features\n", flush=True)
print(f"{'feature':22s} {'dec':4s} | " + " ".join(f"{h}{p}   " for h,p in CELLS) + " | pooled", flush=True)

res = []
for f in FEATS:
    sub = ms.dropna(subset=[f]).copy()
    sub["q"] = sub.groupby("date")[f].transform(
        lambda s: pd.qcut(s.rank(method="first"), 10, labels=False) if s.notna().sum() >= 10 else np.nan)
    for d, tag in ((9, "D10"), (0, "D1")):
        c = cells(sub[sub.q == d])
        ag, ss = score(c)
        line = f"{f:22s} {tag:4s} | {fmt_cells(c)}"
        flag = ""
        if ag >= 5: flag = "  <== 5+/6 cells"
        elif ag >= 4: flag = "  <== 4/6"
        print(line + flag, flush=True)
        res.append((ag, ss, abs(c['ALL'][1]), f, tag, c))

res.sort(reverse=True)
print("\n=== ranked by cells agreeing (|t|>=1.5, pooled sign) ===")
for ag, ss, at, f, tag, c in res[:25]:
    print(f"  {ag}/6 cells (same-sign {ss}/6)  {f:20s} {tag:4s}  {fmt_cells(c)}")
