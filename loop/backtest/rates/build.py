# 금리 국면 검정용 패널 (2026-10-03). 7년 ETF 패널 → 섹터 일수익 + 스타일 + KODEX200, 미국 금리(D-1 미국 종가) 정렬
import pandas as pd, numpy as np, sys, os
LOOP=os.path.expanduser('~/mnt/loop')
sys.path.insert(0, os.path.join(LOOP,'references','scripts'))
import universe_filters as uf, etf_sector_map as sm
p=pd.read_csv(os.path.join(LOOP,'backtest','panel_ohlc_long.csv'),dtype={'code':str})
p['date']=p['date'].astype(str)
nm=p.groupby('code')['name'].last()
keep=[c for c,n in nm.items() if uf.is_spot(n)]
p=p[p['code'].isin(keep)].sort_values(['code','date'])
C=p.pivot(index='date',columns='code',values='close').sort_index()
R=C.pct_change()*100
R=R.where(R.abs()<40)
sec=pd.Series({c:sm.sector(nm[c]) for c in C.columns})
# 선행 20거래일 누적수익(D 종가→D+20 종가). D 종가 매수 기준
F20=(C.shift(-20)/C-1)*100
F1=R.shift(-1)
# 과거 20일 변동성(Rule LV 정렬 변수) · 과거 20일 모멘텀
S20=R.rolling(20,min_periods=15).std()
M20=(C/C.shift(20)-1)*100
pd.to_pickle(dict(C=C,R=R,F20=F20,F1=F1,S20=S20,M20=M20,sec=sec,nm=nm),'/tmp/rates_panel.pkl')
print(C.shape, C.index[0], C.index[-1]); print(sec.value_counts().to_string())
