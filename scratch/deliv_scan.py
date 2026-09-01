"""Pre-screen the delivery-data hypotheses in the 6-cell frame (2 name-halves x 3 regimes).

Bar to justify any engine time, from this session's measured calibration: a day-demeaned t of
+4.8 on a name set produced an engine stable mean_z of only +1.6 there, so a candidate needs
roughly t >= 6 on the HOLD-OUT half before it is worth running.

Every delivery field is already lagged one session in deliv_lab.add_delivery_features.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from deliv_lab import build
from master_lab import report, dayt, CELLS

flat = build(force=True)
print(f"merged rows {len(flat)}", flush=True)
d = flat[flat["mid_small"] & flat["liq"]].copy()
d = d[d["dp"].notna()]
print(f"mid/small rows with lagged delivery: {len(d)}, names {d.ticker.nunique()}, "
      f"dates {d.date.nunique()} {d.date.min().date()}..{d.date.max().date()}\n", flush=True)

# cross-sectional daily ranks
for c in ("dp", "dp_z", "dp_ratio", "ticket_z", "deliv_turnover"):
    d[c + "_r"] = d.groupby("date")[c].rank(pct=True)
d["ram"] = d["change_252d"] / d["vol60"].replace(0, np.nan)
d["ram_r"] = d.groupby("date")["ram"].rank(pct=True)

S = {
 # --- level / rank of delivery itself
 "D6a deliv% top decile":        d.dp_r >= 0.90,
 "D6b deliv% bottom decile":     d.dp_r <= 0.10,
 # --- delivery surprise vs the stock's own norm
 "D1a dp_z > 1.5":               d.dp_z > 1.5,
 "D1b dp_z > 2.5":               d.dp_z > 2.5,
 "D1c dp_z top decile":          d.dp_z_r >= 0.90,
 "D4  dp_z < -1.5 (froth)":      d.dp_z < -1.5,
 "D5  dp_ratio top decile":      d.dp_ratio_r >= 0.90,
 # --- accumulation: high delivery WITH strength
 "D2a dp_z>1.5 & ret1>0":        (d.dp_z > 1.5) & (d.ret1 > 0),
 "D2b dp_z>1.5 & ret5>0":        (d.dp_z > 1.5) & (d.ret5 > 0),
 # --- absorption: high delivery INTO weakness (best a priori)
 "D3a dp_z>1.5 & ret5<0":        (d.dp_z > 1.5) & (d.ret5 < 0),
 "D3b dp_z>1.5 & ret5<-3":       (d.dp_z > 1.5) & (d.ret5 < -3),
 "D3c dp_z>2 & ret5<-5":         (d.dp_z > 2) & (d.ret5 < -5),
 "D3d dp_z>1.5 & rsi<40":        (d.dp_z > 1.5) & (d.rsi < 40),
 # --- block / ticket size (2019+ only)
 "D7  ticket_z > 2":             d.ticket_z > 2,
 "D8  ticket_z>2 & ret1>0":      (d.ticket_z > 2) & (d.ret1 > 0),
 "D8b ticket_z top decile":      d.ticket_z_r >= 0.90,
 # --- does delivery ADD to the best factor found so far (strategy 022)?
 "R0  ram top decile (=022)":    d.ram_r >= 0.90,
 "R1  022 & dp_z>1":             (d.ram_r >= 0.90) & (d.dp_z > 1),
 "R2  022 & dp_z<0":             (d.ram_r >= 0.90) & (d.dp_z < 0),
 "R3  022 & deliv% top half":    (d.ram_r >= 0.90) & (d.dp_r >= 0.5),
 "R4  022 & deliv% bottom half": (d.ram_r >= 0.90) & (d.dp_r < 0.5),
}

print(f"{'setup':34s} {'n':>7s} {'days':>5s} {'edge':>8s} {'t':>6s}  cells", flush=True)
for name, mask in S.items():
    print(report(name, d[mask.fillna(False)]), flush=True)

print("\n=== horizon band for anything with |t| >= 3 ===", flush=True)
for name, mask in S.items():
    sel = d[mask.fillna(False)]
    _, t8, _ = dayt(sel, "fwd8_dm")
    if not np.isfinite(t8) or abs(t8) < 3:
        continue
    line = []
    for h in (6, 8, 10):
        m, t, nd = dayt(sel, f"fwd{h}_dm")
        line.append(f"h{h} {m:+.3f}%/t{t:+5.2f}")
    _, tB, _ = dayt(sel[sel.half == "B"], "fwd8_dm")
    print(f"  {name:32s} " + "  ".join(line) + f"   | hold-out half t{tB:+5.2f}", flush=True)
