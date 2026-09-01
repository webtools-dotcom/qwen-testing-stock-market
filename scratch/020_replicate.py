"""Kill #6 (independent 484-name universe) and kill #7 (held-out forward window) for strategy 020."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategies"))
import importlib
import numpy as np, pandas as pd

m = importlib.import_module("020_turnover_expansion_attention_drift_in_mid_small_caps")

IS_END = m.IS_END
FWD_START = pd.Timestamp("2025-07-01")
FWD_END = pd.Timestamp("2026-08-21")
LO = pd.Timestamp("2000-01-01")

# ---- 1. original 170-name panel, HELD-OUT forward window (never touched during the search)
panel_small = m.prepare(m.load("sector_leadlag_5y"))
fwd = m.slice_panel(panel_small, FWD_START, FWD_END)
print(f"== kill #7: forward window {FWD_START.date()}..{FWD_END.date()} (170-name panel, {len(fwd)} mid/small) ==")
for h in (6, 8, 10):
    s, cf = m.run_set(fwd, horizon=h)
    m.summarize(f"forward h={h}", s, cf)

# ---- 2. broad 484-name universe
print("\nloading broad universe...")
broad = m.prepare(m.load("broad_nse_5y"))
known = set(m.load("sector_leadlag_5y").keys())
new_only = {t: d for t, d in broad.items() if t not in known}
print(f"broad: {len(broad)} names, of which {len(new_only)} were NOT in the search panel")

print(f"\n== kill #6: broad universe, IN-SAMPLE (to {IS_END.date()}) ==")
b_is = m.slice_panel(broad, LO, IS_END)
s, cf = m.run_set(b_is)
m.summarize("broad mid/small h=8", s, cf)

print("\n== kill #6b: only the ~330 names NOT used in the search, in-sample ==")
n_is = m.slice_panel(new_only, LO, IS_END)
s, cf = m.run_set(n_is)
m.summarize("new-names-only h=8", s, cf)

print("\n== broad universe, FORWARD window ==")
b_fwd = m.slice_panel(broad, FWD_START, FWD_END)
for h in (6, 8, 10):
    s, cf = m.run_set(b_fwd, horizon=h)
    m.summarize(f"broad forward h={h}", s, cf)

print("\n== broad universe, full 5y, threshold gradient (h=8) ==")
b_all = m.slice_panel(broad, LO, FWD_END)
for tp in (0.80, 0.85, 0.90, 0.95):
    s, cf = m.run_set(b_all, top_pct=tp)
    m.summarize(f"broad full top {100*(1-tp):.0f}%", s, cf, seeds=10)
