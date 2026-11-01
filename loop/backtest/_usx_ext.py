import json, os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bt_usx_20260821 import load_days, run, avg, folds
days = load_days()
base = run(days, 0, 0); bm = avg(base)
print('baseline %+.4f' % bm)
print('=== lam 확장 (lag0) ===')
for lam in (0.5, 1, 2, 3, 5, 8, 12, 20, 50, 200):
    x = run(days, lam, 0); f = [avg(g) for g in folds(x)]
    print(f'  lam={lam:>5}  full {avg(x):+.4f}   fold {f[0]:+.4f}/{f[1]:+.4f}/{f[2]:+.4f}')
