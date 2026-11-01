# -*- coding: utf-8 -*-
"""채널 위치별 익일 수익률 — 원시(raw) vs 벤치마크 대비 초과(excess) 비교.
raw U자형이 excess에서도 유지되는지가 관건: 유지되면 횡단면 알파, 사라지면 시장타이밍 착시."""
import os, sys, statistics
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from channel_engine import load, Channel, BENCH, LOOKBACKS, LB_LABEL
import bt_channel as BC

HERE = os.path.dirname(os.path.abspath(__file__))
bars, meta, dates, codes = load(os.path.join(HERE, 'ohlc_stock15.csv'))
C = Channel(bars, dates, codes)
bins = [(0.0,0.2),(0.2,0.4),(0.4,0.6),(0.6,0.8),(0.8,0.95),(0.95,1.01)]
labels = ['0.0~0.2 저점권','0.2~0.4','0.4~0.6','0.6~0.8','0.8~0.95','0.95~1.0 고점권']

raw = {N: defaultdict(list) for N in LOOKBACKS}
exc = {N: defaultdict(list) for N in LOOKBACKS}
for i in range(BC.START, len(dates)-1):
    d, dn = dates[i], dates[i+1]
    a, b = C.close(BENCH, d), C.close(BENCH, dn)
    if not (a and b): continue
    bm = b/a - 1.0
    for c in codes:
        x, y = C.close(c, d), C.close(c, dn)
        if not (x and y): continue
        r = y/x - 1.0
        for N in LOOKBACKS:
            pv = C.pos(c, d, N)
            if pv is None: continue
            for bi,(lo,hi) in enumerate(bins):
                if lo <= pv < hi:
                    raw[N][bi].append(r); exc[N][bi].append(r-bm); break

for title, tab in (('원시 익일 수익률 (raw)', raw), ('KODEX200 대비 초과수익 (excess)', exc)):
    print('='*96); print(title); print('='*96)
    print(f"{'채널 위치':18s}" + ''.join(f'{LB_LABEL[N]:>14s}' for N in LOOKBACKS))
    print('-'*96)
    for bi,lab in enumerate(labels):
        cells=[]
        for N in LOOKBACKS:
            xs = tab[N][bi]
            cells.append(f'{statistics.mean(xs)*100:+.3f}%' if len(xs)>=30 else '  -  ')
        print(f'{lab:18s}' + ''.join(c.rjust(14) for c in cells))
    print()
