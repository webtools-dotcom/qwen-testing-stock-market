import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'strategies'))
import importlib.util, numpy as np
spec = importlib.util.spec_from_file_location("s019", "strategies/019_sector_leader_lead_lag_catch_up.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from backtest_engine import edge_vs_control, stable_day_clustered_z
from data_loader import get_panel

panel = get_panel(m.UNIVERSE, period="5y", cache_name="sector_leadlag_5y")
panel = {t: d for t, d in panel.items() if len(d) >= 400}
panel, long = m.build_long(panel)
fol = m.build_signal(long)

for gc, tc in ((0.95, 0.80), (0.85, 0.80)):
    sig = m.signal_rows(fol, gc, tc)
    strat = m.trades_from_rows(sig, panel)
    sec_pool = fol[~fol.index.isin(sig.index)][['row','ticker','date','sector']]
    sec = m.matched_ctrl_factory(sig, sec_pool, ['sector'], panel, base=5000)
    ev = edge_vs_control([x['net_pct'] for x in strat], [x['net_pct'] for x in sec(0)])
    st = stable_day_clustered_z(strat, sec, n_seeds=20)
    print(f"gap>={gc} sector>={tc}: n={len(strat)} net {ev['strategy_avg']:+.3f}% "
          f"sector-matched ctrl {ev['control_avg']:+.3f}% edge {ev['edge']:+.3f}% | "
          f"STABLE mean_z {st['mean_z']:+.2f} pass {st['pass_rate']*100:.0f}%")
    # mid/small subgroup vs random
    sub = [t for t in panel if t not in m.NIFTY_50]
    s = m.trades_from_rows(sig[sig['ticker'].isin(sub)], panel)
    rc = m.random_ctrl_factory([panel[t] for t in sub])
    st2 = stable_day_clustered_z(s, rc, n_seeds=20)
    print(f"    mid/small vs random: n={len(s)} mean_z {st2['mean_z']:+.2f} pass {st2['pass_rate']*100:.0f}%")
