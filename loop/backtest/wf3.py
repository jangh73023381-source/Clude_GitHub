# -*- coding: utf-8 -*-
import pandas as pd, numpy as np
E=pd.read_csv('monthly_excess.csv')
cnt=E.groupby(['sector','month']).size().groupby('sector').min()
LONG=sorted(cnt[cnt>=18].index); L=E[E['sector'].isin(LONG)].copy()

print('=== (4) 순열검정: "최고 조합의 t값"이 우연으로 얼마나 나오나 ===')
def maxt(df,col='excess'):
    g=df.groupby(['sector','month'])[col]
    m=g.mean(); s=g.std(ddof=1); n=g.size()
    t=m/(s/np.sqrt(n))
    return t.abs().max(), t.max()
obs_abs,obs=maxt(L)
rng=np.random.default_rng(11); null=[]
for i in range(2000):
    d=L.copy()
    # 섹터 내에서 월 라벨만 무작위 셔플 (섹터 고유 변동성·시계열 구조 보존)
    d['month']=d.groupby('sector')['month'].transform(lambda s: rng.permutation(s.values))
    null.append(maxt(d)[1])
null=np.array(null)
print(f'  관측 최대 t = {obs:.2f} (반도체 1월)')
print(f'  귀무분포 최대 t 평균 {null.mean():.2f}, 95백분위 {np.percentile(null,95):.2f}')
print(f'  순열 p값 = {np.mean(null>=obs):.3f}  ->  {"유의" if np.mean(null>=obs)<0.05 else "우연으로 충분히 설명됨"}')

print()
print('=== (5) 반도체 1월 이상치 민감도 ===')
x=L[(L.sector=="반도체")&(L.month==1)]['excess'].values
xs=np.sort(x)
print(f'  원본 평균 {x.mean():+.2f}  중앙값 {np.median(x):+.2f}')
print(f'  최대 1개 제거 {np.mean(xs[:-1]):+.2f}  최대 2개 제거 {np.mean(xs[:-2]):+.2f}  상하 10% 절사 {np.mean(xs[3:-3]):+.2f}')
d=[]
for i in range(len(x)):
    y=np.delete(x,i); d.append(y.mean()/(y.std(ddof=1)/np.sqrt(len(y))))
print(f'  잭나이프(1년 제거) t값 범위 [{min(d):.2f}, {max(d):.2f}] -> {"전부 유의" if min(d)>2.06 else "일부 유의성 상실"}')

print()
print('=== (6) 매매 가능 수단(섹터 ETF)에서 1월 재현 확인 ===')
p=pd.read_csv('/sessions/quirky-kind-fermi/mnt/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
p['date']=pd.to_datetime(p['date'],format='%Y%m%d')
w=p.pivot_table(index='date',columns='code',values='close')
m=w.resample('ME').last().pct_change()*100
PAIR={'091160':'KODEX 반도체','091230':'TIGER 반도체','091170':'KODEX 은행','091180':'KODEX 자동차',
      '102970':'KODEX 증권','117700':'KODEX 건설','228790':'TIGER 화장품','244580':'KODEX 바이오',
      '266370':'KODEX IT','305720':'KODEX 2차전지산업'}
b=m['069500']
print('  ETF                 1월 n  1월평균  승률 | 전월평균(참고)')
for c,n in PAIR.items():
    if c not in m: continue
    ex=(m[c]-b).dropna(); j=ex[ex.index.month==1]
    print(f'  {n:<18} {len(j):4d}  {j.mean():+7.2f}  {(j>0).mean()*100:5.1f}% | {ex.mean():+6.2f}')
