import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_loader import get_panel
from universe500 import UNIVERSE
p = get_panel(UNIVERSE, period="5y", cache_name="broad_nse_5y")
print("fetched", len(p))
