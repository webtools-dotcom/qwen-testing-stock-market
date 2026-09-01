"""Does excluding low-delivery names sharpen 022? The exclusion must keep breadth: a filter that
halves the sample cannot help, because the statistic is breadth-limited (measured earlier)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from deliv_lab import build
from master_lab import report, dayt

d = build()
d = d[d["mid_small"] & d["liq"]].copy()
d = d[d["dp"].notna()]
d["ram"] = d["change_252d"] / d["vol60"].replace(0, np.nan)
d["ram_r"] = d.groupby("date")["ram"].rank(pct=True)
d["dp_r"] = d.groupby("date")["dp"].rank(pct=True)
top = d["ram_r"] >= 0.90

V = {
 "base 022 top decile":            top,
 "022 excl dp_z < -1.5":           top & ~(d.dp_z < -1.5),
 "022 excl dp_z < -1.0":           top & ~(d.dp_z < -1.0),
 "022 excl dp_z < -0.5":           top & ~(d.dp_z < -0.5),
 "022 excl dp bottom decile":      top & ~(d.dp_r <= 0.10),
 "022 excl dp bottom quintile":    top & ~(d.dp_r <= 0.20),
 "022 excl dp bottom 30%":         top & ~(d.dp_r <= 0.30),
 "022 excl dp<20% absolute":       top & ~(d.dp < 20),
 "022 excl dp<30% absolute":       top & ~(d.dp < 30),
}
print(f"{'variant':34s} {'n':>7s} {'days':>5s} {'edge':>8s} {'t':>6s}  cells", flush=True)
for k, m in V.items():
    print(report(k, d[m.fillna(False)]), flush=True)

print("\n=== hold-out half B and horizon band ===", flush=True)
for k, m in V.items():
    sel = d[m.fillna(False)]
    _, tB, _ = dayt(sel[sel.half == "B"], "fwd8_dm")
    row = []
    for h in (6, 8, 10):
        mm, tt, _ = dayt(sel, f"fwd{h}_dm")
        row.append(f"h{h} {mm:+.3f}%/t{tt:+5.2f}")
    kept = 100 * len(sel) / max(1, len(d[top.fillna(False)]))
    print(f"  {k:32s} " + "  ".join(row) + f"  | halfB t{tB:+5.2f}  keeps {kept:.0f}%", flush=True)
