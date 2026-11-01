# -*- coding: utf-8 -*-
"""(1) 확장윈도 워크포워드 전략 (2) 시장 자체 월별 계절성 (3) 최강 후보 부트스트랩"""
import pandas as pd, numpy as np
from scipy import stats as st
E=pd.read_csv('monthly_excess.csv')
cnt=E.groupby(['sector','month']).size().groupby('sector').min()
LONG=sorted(cnt[cnt>=18].index)
L=E[E['sector'].isin(LONG)].copy()

print('=== (1) 확장윈도 워크포워드: 매년 그 달 과거성적 1위 섹터 매수 ===')
print('    (룩어헤드 없음 — t년 m월 진입 시 t-1년까지의 데이터만 사용, 최소 8년 누적 후 시작)')
for topk in (1,2,3):
    res=[]
    for yr in range(2010,2027):
        for mo in range(1,13):
            past=L[(L.year<yr)&(L.month==mo)]
            g=past.groupby('sector')['excess'].agg(['mean','size'])
            g=g[g['size']>=8]
            if len(g)<5: continue
            picks=g.sort_values('mean',ascending=False).head(topk).index.tolist()
            cur=L[(L.year==yr)&(L.month==mo)&(L.sector.isin(picks))]
            if len(cur)==0: continue
            res.append(dict(ym=f'{yr}-{mo:02d}',ex=cur['excess'].mean(),n=len(cur)))
    r=pd.DataFrame(res)
    x=r['ex'].values; t=x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))
    print(f'  top{topk}: n={len(x):3d}개월  월평균 코스피대비 {x.mean():+6.3f}%p  t={t:+5.2f}  승률 {(x>0).mean()*100:5.1f}%  누적 {np.prod(1+x/100)-1:+7.1%}')
    if topk==1: r.to_csv('wf_strategy.csv',index=False)

print()
print('=== (1b) 역방향(과거 최악 섹터 매수) 대조 ===')
res=[]
for yr in range(2010,2027):
    for mo in range(1,13):
        past=L[(L.year<yr)&(L.month==mo)]
        g=past.groupby('sector')['excess'].agg(['mean','size']); g=g[g['size']>=8]
        if len(g)<5: continue
        picks=g.sort_values('mean').head(1).index.tolist()
        cur=L[(L.year==yr)&(L.month==mo)&(L.sector.isin(picks))]
        if len(cur): res.append(cur['excess'].mean())
x=np.array(res); print(f'  worst1: n={len(x)}  월평균 {x.mean():+6.3f}%p  t={x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+5.2f}  승률 {(x>0).mean()*100:.1f}%')

print()
print('=== (2) 코스피 지수 자체의 월별 계절성 (2000-01~2026-08) ===')
d=pd.read_csv('px.csv'); d['date']=pd.to_datetime(d['date'])
ks=d[d.code=='^KS11'].set_index('date')['close'].resample('ME').last().pct_change().dropna()*100
kq=d[d.code=='^KQ11'].set_index('date')['close'].resample('ME').last().pct_change().dropna()*100
out=[]
for mo in range(1,13):
    a=ks[ks.index.month==mo].values; b=kq[kq.index.month==mo].values
    ta=a.mean()/(a.std(ddof=1)/np.sqrt(len(a)))
    out.append(dict(month=mo,n=len(a),kospi_mean=a.mean(),kospi_t=ta,kospi_win=(a>0).mean()*100,
                    kosdaq_mean=b.mean(),kosdaq_win=(b>0).mean()*100))
O=pd.DataFrame(out)
print(O.to_string(index=False,float_format=lambda v:f'{v:7.2f}'))
p=2*(1-st.t.cdf(O.kospi_t.abs(),O.n-1))
print('  최소 p값 %.3f (12검정 중 Bonferroni 임계 0.0042) -> %s'%(p.min(),'유의' if p.min()<0.0042 else '유의하지 않음'))
O.to_csv('market_month.csv',index=False)

print()
print('=== (3) 최강 후보 "반도체 1월" 블록 부트스트랩 (연 단위 리샘플, 10,000회) ===')
x=L[(L.sector=='반도체')&(L.month==1)]['excess'].values
rng=np.random.default_rng(7); bs=[rng.choice(x,len(x),replace=True).mean() for _ in range(10000)]
lo,hi=np.percentile(bs,[2.5,97.5])
print(f'  n={len(x)}  평균 {x.mean():+.2f}%p  95% CI [{lo:+.2f}, {hi:+.2f}]  P(평균>0)={np.mean(np.array(bs)>0)*100:.1f}%')
print(f'  전반 2000-2015 평균 {x[:15].mean():+.2f}%p / 후반 2016-2026 평균 {x[15:].mean():+.2f}%p')
print(f'  연도별: '+', '.join(f'{v:+.0f}' for v in x))
