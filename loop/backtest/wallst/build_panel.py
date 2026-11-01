import pandas as pd, numpy as np, sys, os, json
LOOP=os.path.expanduser('~/mnt/loop')
sys.path.insert(0, os.path.join(LOOP,'references','scripts'))
import universe_filters as uf, etf_sector_map as sm
import inspect
print(inspect.signature(uf.eligible))
p=pd.read_csv(os.path.join(LOOP,'backtest','panel_ohlc_long.csv'),dtype={'code':str})
p['date']=p['date'].astype(str)
nm=p.groupby('code')['name'].last()
keep=[c for c,n in nm.items() if uf.is_spot(n)]
print("codes total",len(nm),"spot",len(keep))
p=p[p['code'].isin(keep)].copy()
p['sector']=p['code'].map(lambda c: sm.sector(nm[c]))
p=p.sort_values(['code','date'])
p['ret']=p.groupby('code')['close'].pct_change()*100
p=p.dropna(subset=['ret'])
p=p[p['ret'].abs()<40]
sec=p.groupby(['date','sector'])['ret'].agg(['mean','count']).reset_index()
sec=sec[sec['count']>=2]
sec.to_csv('kr_sector_daily.csv',index=False)
allk=p.groupby('date')['ret'].mean().rename('KR_ALL')
allk.to_csv('kr_all_daily.csv')
print(sec['sector'].value_counts().to_string())
print("days",sec['date'].nunique(),sec['date'].min(),sec['date'].max())
