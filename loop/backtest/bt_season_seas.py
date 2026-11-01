# -*- coding: utf-8 -*-
"""섹터 월별 계절성 검정 (조회 전용 데이터 기반)."""
import pandas as pd, numpy as np, json
pd.options.mode.chained_assignment=None

d=pd.read_csv('px.csv')
d['date']=pd.to_datetime(d['date'])
name={c:n for c,n in zip(d['code'],d['name'])}
sect={c:s for c,s in zip(d['code'],d['sector'])}
p=d.pivot_table(index='date',columns='code',values='close')

# 월말 종가 -> 월간 수익률
m=p.resample('ME').last()
mret=m.pct_change()*100.0
bench=mret['^KS11']

codes=[c for c in m.columns if c not in ('^KS11','^KQ11')]
recs=[]
for c in codes:
    s=mret[c].dropna()
    ex=(s-bench).dropna()
    for dt,v in ex.items():
        recs.append(dict(code=c,sector=sect[c],name=name[c],ym=dt.strftime('%Y-%m'),
                         year=dt.year,month=dt.month,excess=v,raw=s.loc[dt],bench=bench.loc[dt]))
E=pd.DataFrame(recs)
E.to_csv('monthly_excess.csv',index=False)

def stats(g):
    x=g['excess'].values
    n=len(x); mu=x.mean(); sd=x.std(ddof=1) if n>1 else np.nan
    t=mu/(sd/np.sqrt(n)) if n>1 and sd>0 else np.nan
    return pd.Series(dict(n=n,mean=mu,sd=sd,t=t,win=(x>0).mean()*100,med=np.median(x)))

full=E.groupby(['sector','month']).apply(stats,include_groups=False).reset_index()
full=full.sort_values('t',ascending=False)
full.to_csv('full_sample.csv',index=False)

print('=== 표본 개요 ===')
cov=E.groupby('sector').agg(n_month=('excess','size'),first=('ym','min'),last=('ym','max'))
print(cov.sort_values('n_month',ascending=False).to_string())
print()
print('=== 전체기간 in-sample 상위 12 (t값 기준) ===')
print(full.head(12).to_string(index=False,float_format=lambda v:f'{v:7.2f}'))
print()
print('=== 전체기간 in-sample 하위 8 ===')
print(full.tail(8).to_string(index=False,float_format=lambda v:f'{v:7.2f}'))
