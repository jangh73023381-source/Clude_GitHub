import sys; sys.path.insert(0,'/home/claude/w/loop/backtest/loop10_20260926')
import os; os.chdir('/home/claude/w/loop/backtest/loop10_20260926')
from engine import *
import mid
E=mid.E
for nm,f in [('LV',E.sel_lv),('MOM',E.sel_mom)]:
    df=E.run(f)
    for m in ('OO','A','L1'):
        p=prof(df[m]); print(nm,m,f"{p['cagr']:+.1f} {p['mdd']:.1f} {p['sharpe']:.2f}")
o,_=mid.report('mom150 tranche',mid.base_sel)
