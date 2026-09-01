import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from macro_lab import build, dayt, FACTORS

flat = build(force=True)
print(f"rows {len(flat)}, names {flat.ticker.nunique()}, dates {flat.date.nunique()}, "
      f"{flat.date.min().date()}..{flat.date.max().date()}", flush=True)

IS_END = pd.Timestamp("2022-12-31")     # search period
ms = flat[flat["mid_small"]].copy()

def tri(sel, col="fwd8_dm"):
    out = []
    for name, s in (("S", sel[(sel.half == "A") & (sel.date <= IS_END)]),
                    ("U", sel[(sel.half == "B") & (sel.date <= IS_END)]),
                    ("T", sel[sel.date > IS_END])):
        m, t, n = dayt(s, col)
        out.append(f"{name} {m:+.3f}%/t{t:+5.2f}/d{n:4d}")
    return "  ".join(out)

def dec(df, col, n=10):
    return df.groupby("date")[col].transform(
        lambda s: pd.qcut(s.rank(method="first"), n, labels=False) if s.notna().sum() >= n else np.nan)

print("\n=== composite macro_score decile ladder ===", flush=True)
sub = ms.dropna(subset=["macro_score"]).copy()
sub["q"] = dec(sub, "macro_score")
for d in range(10):
    print(f"  D{d+1:<3d} {tri(sub[sub.q == d])}", flush=True)

print("\n=== per-factor: beta_f * move_f, top and bottom decile ===", flush=True)
for f in FACTORS:
    s = ms.dropna(subset=[f"beta_{f}", f"mv_{f}"]).copy()
    s["c"] = s[f"beta_{f}"] * s[f"mv_{f}"]
    s["q"] = dec(s, "c")
    print(f"  {f:8s} D10 {tri(s[s.q == 9])}", flush=True)
    print(f"  {f:8s}  D1 {tri(s[s.q == 0])}", flush=True)

print("\n=== plain beta deciles (is it just a factor-exposure premium?) ===", flush=True)
for f in FACTORS:
    s = ms.dropna(subset=[f"beta_{f}"]).copy()
    s["q"] = dec(s, f"beta_{f}")
    print(f"  {f:8s} beta D10 {tri(s[s.q == 9])}", flush=True)
