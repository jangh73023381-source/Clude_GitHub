#!/usr/bin/env python3
"""Rule EG 검토용 캐시 — 7년 패널(2019-04~) OHLCV + 지표 + 신호를 pickle 로 저장 (조회 전용)."""
import os, sys, pickle, time
import numpy as np, pandas as pd
t0=time.time()
LOOP=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(LOOP,'references','scripts'))
import universe_filters as uf
from etf_sector_map import sector
lg=pd.read_csv(os.path.join(LOOP,'backtest','panel_ohlc_long.csv'),dtype={'code':str})
t2=pd.read_csv(os.path.join(LOOP,'backtest','panel_ohlc_2y.csv'),dtype={'code':str})
p=pd.concat([lg,t2[t2.date>lg.date.max()][lg.columns]],ignore_index=True)
p=p.drop_duplicates(['code','date']).sort_values(['code','date'])
p=p[~p.name.map(lambda n: uf.is_deriv(n) or uf.is_cash(n))]
dates=np.array(sorted(p.date.unique()))
di={d:i for i,d in enumerate(dates)}
N=len(dates); codes=sorted(p.code.unique()); M=len(codes)
arr={k:np.full((M,N),np.nan) for k in ['O','H','L','C','V']}
names={}
for m,(code,d) in enumerate(p.groupby('code')):
    idx=d.date.map(di).values
    for k,col in zip('OHLCV',['open','high','low','close','volume']):
        arr[k][m,idx]=d[col].values
    names[code]=d.name.iloc[0]
codes=[c for c,_ in p.groupby('code')]
C,O,H,L,V=arr['C'],arr['O'],arr['H'],arr['L'],arr['V']
def roll_mean(x,w):
    df=pd.DataFrame(x.T); return df.rolling(w,min_periods=w).mean().values.T
def roll_min(x,w):
    df=pd.DataFrame(x.T); return df.rolling(w,min_periods=w).min().values.T
MA20=roll_mean(C,20); MA60=roll_mean(C,60); VA=roll_mean(V,20); L5=roll_min(L,5)
AMT=roll_mean(C*V,20)
def sh(x,k):
    y=np.full_like(x,np.nan); y[:,k:]=x[:,:-k]; return y
trend=(C>=MA20)&(MA20>sh(MA20,1))&(C>MA60)&(MA60>=sh(MA60,5))&(L5<=MA20*1.02)
eg=trend&(C>=sh(O,1))&(C>O)&(sh(C,1)<sh(O,1))&(C>=L+(H-L)*0.6)&(V>=VA*1.3)
eg=np.nan_to_num(eg,nan=False).astype(bool); trend=np.nan_to_num(trend,nan=False).astype(bool)
# 거래대금 순위(일별, 20일 평균 거래대금 기준)
rank=np.full((M,N),np.nan)
for j in range(N):
    col=AMT[:,j]; ok=~np.isnan(col)
    r=np.empty(ok.sum()); r[np.argsort(-col[ok])]=np.arange(1,ok.sum()+1); rank[ok,j]=r
k=pd.read_csv(os.path.join(LOOP,'backtest','kospi_close.csv'))
# KODEX200 069500 as bench if present
bench=None
if '069500' in codes: bench=C[codes.index('069500')]
secs=[sector(names[c]) for c in codes]
out=dict(dates=dates,codes=codes,names=names,secs=secs,O=O,H=H,L=L,C=C,V=V,MA20=MA20,MA60=MA60,VA=VA,AMT=AMT,rank=rank,trend=trend,eg=eg,bench=bench)
pickle.dump(out,open(os.path.join(LOOP,'backtest','eg_review','_eg_cache.pkl'),'wb'))
print('dates',dates[0],dates[-1],N,'codes',M,'signals',eg.sum(),'trend days',trend.sum(),'bench',bench is not None, f'{time.time()-t0:.1f}s')
