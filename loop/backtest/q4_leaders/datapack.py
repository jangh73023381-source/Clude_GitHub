import sys,os,json,warnings; warnings.filterwarnings('ignore')
sys.path.insert(0,'references/scripts')
import pandas as pd,numpy as np
from etf_sector_map import sector
from universe_filters import is_deriv,is_cash
out={}
def load(p):
    d=pd.read_csv(p,dtype={'code':str}); d=d[~d.name.map(lambda n:is_deriv(n) or is_cash(n))]; return d
s=load('backtest/panel_ohlc_2y.csv')
C=s.pivot(index='date',columns='code',values='close').sort_index(); V=s.pivot(index='date',columns='code',values='volume').sort_index()
nm=s.drop_duplicates('code').set_index('code').name
D=C.index[-1]; i=len(C)-1
def mom(k): return (C.iloc[-1]/C.iloc[-1-k]-1)*100
tv=(C*V).iloc[-20:].mean()/1e8
df=pd.DataFrame({'name':nm,'sec':nm.map(sector),'m20':mom(20),'m60':mom(60),'m120':mom(120),'tv20_억':tv})
g=df.groupby('sec').agg(n=('name','size'),m20=('m20','median'),m60=('m60','median'),m120=('m120','median'),tv=('tv20_억','sum')).round(1).sort_values('m60',ascending=False)
out['asof']=int(D); out['sector_mom']=g.reset_index().to_dict('records')
k200=C['069500']; out['kodex200']={'m20':round(mom(20)['069500'],1),'m60':round(mom(60)['069500'],1),'m120':round(mom(120)['069500'],1),'close':float(k200.iloc[-1]),'ma60':round(float(k200.iloc[-60:].mean()),0),'ma120':round(float(k200.iloc[-120:].mean()),0)}
top=df.dropna().sort_values('m60',ascending=False).head(15).round(1)
out['top_etf_m60']=top.reset_index().rename(columns={'index':'code'}).to_dict('records')
# 7년 계절성
L=load('backtest/panel_ohlc_long.csv'); L['ym']=L.date//100
M=L.sort_values('date').groupby(['code','ym']).close.last().unstack()
ret=M.pct_change(axis=1)*100
secs=L.drop_duplicates('code').set_index('code').name.map(sector)
seas={}
for y in range(2019,2026):
    for mth in (10,11,12):
        col=y*100+mth
        if col not in ret.columns: continue
        r=ret[col].dropna(); k=r.get('069500',np.nan)
        for sc,v in r.groupby(secs).median().items():
            seas.setdefault(sc,{}).setdefault(mth,[]).append(round(v-k,2))
out['q4_seasonality_vs_kodex200']={sc:{m:{'mean':round(float(np.mean(v)),2),'hit':f"{sum(x>0 for x in v)}/{len(v)}"} for m,v in d.items()} for sc,d in seas.items()}
# 모멘텀 지속성: 7~9월 섹터 순위 → Q4 성과(섹터 중앙값, KODEX200 대비)
pers=[]
for y in range(2019,2026):
    q3=[y*100+m for m in (7,8,9)]; q4=[y*100+m for m in (10,11,12)]
    if not all(c in ret.columns for c in q3+q4): continue
    r3=((1+ret[q3]/100).prod(axis=1)-1)*100; r4=((1+ret[q4]/100).prod(axis=1)-1)*100
    a=pd.DataFrame({'q3':r3.groupby(secs).median(),'q4':r4.groupby(secs).median(),'n':r3.groupby(secs).size()}).dropna(); a=a[a.n>=2]
    k4=r4.get('069500',np.nan); a=a.sort_values('q3',ascending=False)
    pers.append({'year':y,'k200_q4':round(float(k4),1),'top3_q3':list(a.index[:3]),'top3_q4_vs_k200':round(float(a.q4[:3].mean()-k4),1),'bot3_q4_vs_k200':round(float(a.q4[-3:].mean()-k4),1),'rank_corr':round(float(a.q3.rank().corr(a.q4.rank())),2),'nsec':len(a)})
out['q3_to_q4_persistence']=pers
# 코스피 Q4 월별
k=pd.read_csv('backtest/kospi_close.csv'); print(k.columns.tolist())
json.dump(out,open('backtest/q4_leaders/datapack.json','w'),ensure_ascii=False,indent=1,default=float)
print(json.dumps(out,ensure_ascii=False,default=float)[:6000])
