#!/usr/bin/env python3
"""매도 타점·매수 금지(Sell-Ban) 검정용 캐시 — 7년 패널 OHLCV 행렬 + 공용 지표 (조회 전용, 2026-09-11).
eg_review/build_cache.py 와 같은 패널 결합·유니버스 필터를 쓴다(아침 루틴과 동일 universe_filters)."""
import os, sys, pickle, time
import numpy as np, pandas as pd
t0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
import universe_filters as uf
from etf_sector_map import sector
lg = pd.read_csv(os.path.join(LOOP, 'backtest', 'panel_ohlc_long.csv'), dtype={'code': str})
t2 = pd.read_csv(os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv'), dtype={'code': str})
p = pd.concat([lg, t2[t2.date > lg.date.max()][lg.columns]], ignore_index=True)
p = p.drop_duplicates(['code', 'date']).sort_values(['code', 'date'])
p = p[~p.name.map(lambda n: uf.is_deriv(n) or uf.is_cash(n))]
dates = np.array(sorted(p.date.unique())); di = {d: i for i, d in enumerate(dates)}
N = len(dates); codes = [c for c, _ in p.groupby('code')]; M = len(codes)
A = {k: np.full((M, N), np.nan) for k in 'OHLCV'}
names = {}
for m, (code, d) in enumerate(p.groupby('code')):
    idx = d.date.map(di).values
    for k, col in zip('OHLCV', ['open', 'high', 'low', 'close', 'volume']):
        A[k][m, idx] = d[col].values
    names[code] = d.name.iloc[0]
# 가격 0/음수는 결손 처리
for k in 'OHLC':
    A[k][A[k] <= 0] = np.nan
out = dict(dates=dates, codes=codes, names=names, secs=[sector(names[c]) for c in codes], **A)
pickle.dump(out, open(os.path.join(HERE, '_sb_cache.pkl'), 'wb'))
print('dates', dates[0], dates[-1], N, 'codes', M, f'{time.time()-t0:.1f}s')
