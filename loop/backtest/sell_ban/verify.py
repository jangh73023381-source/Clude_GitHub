#!/usr/bin/env python3
"""독립 재계산 — 캐시·engine 을 쓰지 않고 원본 CSV 에서 F14(역배열 진입, 금지 20일) 이벤트 성과를 다시 계산한다."""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); LOOP = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
import universe_filters as uf
lg = pd.read_csv(os.path.join(LOOP, 'backtest', 'panel_ohlc_long.csv'), dtype={'code': str})
t2 = pd.read_csv(os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv'), dtype={'code': str})
p = pd.concat([lg, t2[t2.date > lg.date.max()][lg.columns]]).drop_duplicates(['code', 'date'])
p = p[~p.name.map(lambda n: uf.is_deriv(n) or uf.is_cash(n))]
wide = p.pivot(index='date', columns='code', values='close').sort_index()
wide = wide.where(wide > 0)
ma = {w: wide.rolling(w, min_periods=w).mean() for w in (5, 20, 60)}
state = (ma[5] < ma[20]) & (ma[20] < ma[60])
sig = state & ~state.shift(1, fill_value=False)
fwd = wide.shift(-21) / wide.shift(-1) - 1                 # D+1 종가 → D+21 종가
exc = fwd.sub(fwd.mean(axis=1), axis=0)
ev = exc[sig].stack()
raw = fwd[sig].stack()
print('F14 events', len(ev), 'mean excess %.3f%%p' % (ev.mean() * 100), 'P(underperform) %.1f%%' % ((ev < 0).mean() * 100),
      'raw mean %.2f%%' % (raw.mean() * 100), 'P(raw<0) %.1f%%' % ((raw < 0).mean() * 100))
allraw = fwd.stack()
print('universe all stock-days raw 20d mean %.2f%%  P(raw<0) %.1f%%' % (allraw.mean() * 100, (allraw < 0).mean() * 100))
# 룩어헤드 점검: 신호일 D 의 MA 는 D 까지만 사용(rolling 은 과거 창) · 수익 창은 D+1 이후만 사용
d0 = sig.index[sig.any(axis=1)][100]; c0 = sig.columns[sig.loc[d0]][0]
s = wide[c0].dropna(); i = s.index.get_loc(d0)
print('spot', c0, d0, 'MA5/20/60 at D', round(s.iloc[i-4:i+1].mean(), 1), round(s.iloc[i-19:i+1].mean(), 1), round(s.iloc[i-59:i+1].mean(), 1),
      '| cache MA', round(ma[5].loc[d0, c0], 1), round(ma[20].loc[d0, c0], 1), round(ma[60].loc[d0, c0], 1))
# 섹터별 분포
from etf_sector_map import sector
names = p.drop_duplicates('code').set_index('code').name
e = ev.reset_index(); e.columns = ['date', 'code', 'x']; e['sec'] = e.code.map(lambda c: sector(names[c]))
g = e.groupby('sec').x.agg(['count', 'mean']).sort_values('count', ascending=False)
g['mean'] *= 100
print(g.head(12).round(2).to_string())
