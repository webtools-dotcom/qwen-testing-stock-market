import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from deliv_lab import build
from master_lab import dayt

d = build(); d = d[d["mid_small"] & d["liq"]].copy(); d = d[d["dp"].notna()]
d["ram"] = d["change_252d"] / d["vol60"].replace(0, np.nan)
d["ram_r"] = d.groupby("date")["ram"].rank(pct=True)
top = d["ram_r"] >= 0.90
base = d[top.fillna(False)]
filt = d[(top & ~(d.dp_z < -1.0)).fillna(False)]

print("=== per-year: base 022 vs delivery-filtered ===")
print(f"{'year':6s} {'base edge/t':>20s} {'filtered edge/t':>20s}")
for y in sorted(base.date.dt.year.unique()):
    b = dayt(base[base.date.dt.year == y]); f = dayt(filt[filt.date.dt.year == y])
    print(f"{y:6d} {b[0]:+8.3f}%/t{b[1]:+6.2f}   {f[0]:+8.3f}%/t{f[1]:+6.2f}")

print("\n=== the periods where base 022 was weakest ===")
for lbl, lo, hi in (("2018-04..2019-12 (fold1)", "2018-04-23", "2019-12-30"),
                    ("2019-12..2021-08 (fold2)", "2019-12-30", "2021-08-25"),
                    ("2021-08..2023-04 (fold3)", "2021-08-25", "2023-04-25"),
                    ("2023-04..2024-12 (fold4)", "2023-04-25", "2024-12-26"),
                    ("2024-12..2026-08 (fold5)", "2024-12-26", "2026-08-20")):
    lo, hi = pd.Timestamp(lo), pd.Timestamp(hi)
    b = dayt(base[(base.date >= lo) & (base.date <= hi)])
    f = dayt(filt[(filt.date >= lo) & (filt.date <= hi)])
    print(f"  {lbl:26s} base {b[0]:+.3f}%/t{b[1]:+5.2f}  ->  filtered {f[0]:+.3f}%/t{f[1]:+5.2f}")
