# -*- coding: utf-8 -*-
"""0.5% 트레일링 스톱(절반 매도) vs 방치 — 7년 ETF 패널 실측."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/'.join([__import__('os').environ['HOME'],'mnt/loop/references/scripts']))
from universe_filters import eligible

P = __import__('os').environ['HOME'] + '/mnt/loop/backtest/panel_ohlc_long.csv'
df = pd.read_csv(P, dtype={'code':str})
df = df[df['name'].map(eligible)]
df = df.sort_values(['code','date'])
BAND = 0.005
HS = [5,10,20]
out = {}

rows = []
for code, g in df.groupby('code', sort=False):
    if len(g) < 60: continue
    o = g['open'].to_numpy(float); h = g['high'].to_numpy(float)
    l = g['low'].to_numpy(float);  c = g['close'].to_numpy(float)
    d = g['date'].to_numpy()
    n = len(c)
    for H in HS:
        m = n - H          # 진입 가능 인덱스 0..m-1
        if m <= 0: continue
        C0 = c[:m]
        CH = c[H:H+m]
        peak_excl = C0.copy()                 # 당일 고가 제외 러닝피크
        first_t = np.zeros(m, dtype=int)      # 0 = 미발동
        fill = np.zeros(m)
        c_t  = np.zeros(m); c_t1 = np.zeros(m)
        for t in range(1, H+1):
            hi = h[t:t+m]; lo = l[t:t+m]; op = o[t:t+m]
            peak_incl = np.maximum(peak_excl, hi)
            stop = peak_incl * (1-BAND)       # 체크 시점 기준 재설정(사용자 방식에 가까움)
            hit = (first_t == 0) & (lo <= stop)
            if hit.any():
                f = np.where(op < stop, op, stop)
                first_t[hit] = t
                fill[hit] = f[hit]
                c_t[hit] = c[t:t+m][hit]
                nxt = c[min(t+1,n-1):min(t+1,n-1)+m]
                c_t1[hit] = (nxt[hit] if t+1 <= H else CH[hit])
            peak_excl = peak_incl
        rows.append(pd.DataFrame({
            'code':code,'H':H,'date':d[:m],'C0':C0,'CH':CH,
            't':first_t,'fill':fill,'ct':c_t,'ct1':c_t1}))

R = pd.concat(rows, ignore_index=True)
R.to_pickle(__import__('os').environ['HOME']+'/work/ep.pkl')
print('episodes', len(R))
