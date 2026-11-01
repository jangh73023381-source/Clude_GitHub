# -*- coding: utf-8 -*-
"""ETF 설정/환매 축 — 유니버스 정합 + 모멘텀/거래량 통제 + fold + R5 + 대조군."""
import sys,os
import pandas as pd, numpy as np
from math import erf,sqrt
HERE=os.path.dirname(os.path.abspath(__file__)); LOOP=os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0,os.path.join(LOOP,'references','scripts'))
import universe_filters as uf
def _spear(x,y):
    rx=pd.Series(x).rank().values; ry=pd.Series(y).rank().values
    r=np.corrcoef(rx,ry)[0,1]; n=len(rx); t=r*np.sqrt((n-2)/max(1-r*r,1e-12))
    return r, 2*(1-0.5*(1+erf(abs(t)/sqrt(2))))
def _tt(a,b):
    a,b=np.asarray(a),np.asarray(b)
    se=np.sqrt(a.var(ddof=1)/len(a)+b.var(ddof=1)/len(b))
    t=(a.mean()-b.mean())/max(se,1e-12)
    return t, 2*(1-0.5*(1+erf(abs(t)/sqrt(2))))
def pcorr(x,y,c):
    rx,ry,rc=[pd.Series(v).rank().values for v in (x,y,c)]
    rxy=np.corrcoef(rx,ry)[0,1]; rxc=np.corrcoef(rx,rc)[0,1]; ryc=np.corrcoef(ry,rc)[0,1]
    return (rxy-rxc*ryc)/np.sqrt(max((1-rxc**2)*(1-ryc**2),1e-12))

df=pd.read_csv(os.path.join(LOOP,'backtest','krx_etf_panel.csv'),dtype={'code':str,'date':str})
n0=df.code.nunique()
df=df[df.name.map(uf.eligible)]
print(f'유니버스 {n0} → {df.code.nunique()}종 (레버리지·인버스·현금성 제외)')
df=df.sort_values(['code','date'])
g=df.groupby('code')
df['shrs_chg']=g.list_shrs.pct_change()
df['ret1']=g.close.pct_change()
df['mom5']=g.close.pct_change(5)
df['vol_rel']=df.volume/g.volume.transform(lambda s:s.rolling(20,min_periods=5).mean())
df['fwd1']=g.close.shift(-1)/df.close-1
bench=df.groupby('date').fwd1.mean().rename('bench')
df=df.merge(bench,on='date',how='left'); df['exc']=df.fwd1-df.bench
gg=df.groupby('code')
df['sig']=gg.shrs_chg.shift(1)      # D-1 설정/환매 (실전 조달 가능)
df['ret1_lag']=gg.ret1.shift(1); df['mom5_lag']=gg.mom5.shift(1); df['vol_lag']=gg.vol_rel.shift(1)
d=df.dropna(subset=['sig','exc']).copy(); d=d[d.sig.abs()>1e-9]
print(f'관측 {len(d):,}건 · {d.date.nunique()}거래일 · {d.code.nunique()}종')

def quint(z,sig='sig',lbl=''):
    z=z.copy(); z['q']=pd.qcut(z[sig].rank(method='first'),5,labels=False)
    m=z.groupby('q').exc.mean()*100
    tv,tp=_tt(z[z.q==4].exc.values,z[z.q==0].exc.values)
    r,p=_spear(z[sig].values,z.exc.values)
    print(f'{lbl:<26} n={len(z):6,}  rho={r:+.4f}(p={p:.3f})  5분위: '+' / '.join(f'{v:+.3f}' for v in m)+f'   Q5-Q1 {m.iloc[-1]-m.iloc[0]:+.3f}%p t={tv:+.2f} p={tp:.3f}')
    return m.iloc[-1]-m.iloc[0]

print('\n'+'='*112); print('1. 유니버스 정합 후 재현'); print('='*112)
base=quint(d,lbl='[D-1] 상장좌수 변화율')

print('\n'+'='*112); print('2. R2 — 3분할 fold (114거래일을 전·중·후로)'); print('='*112)
ds=sorted(d.date.unique()); n=len(ds); cuts=[ds[:n//3],ds[n//3:2*n//3],ds[2*n//3:]]
for i,c in enumerate(cuts,1):
    quint(d[d.date.isin(c)],lbl=f'  fold{i} ({c[0]}~{c[-1]})')

print('\n'+'='*112); print('3. 모멘텀·거래량 통제 (부분상관)'); print('='*112)
z=d.dropna(subset=['ret1_lag','mom5_lag','vol_lag'])
print(f'  단순 sig→exc                 rho={_spear(z.sig.values,z.exc.values)[0]:+.4f}')
for c,lbl in [('ret1_lag','전일 수익률'),('mom5_lag','5일 모멘텀'),('vol_lag','상대거래량')]:
    print(f'  {lbl} 통제 후            rho={pcorr(z.sig.values,z.exc.values,z[c].values):+.4f}')

print('\n'+'='*112); print('4. R5 — 꼬리 기여도 (Q5-Q1 스프레드 일별 분해)'); print('='*112)
z=d.copy(); z['q']=z.groupby('date').sig.transform(lambda s: pd.qcut(s.rank(method='first'),5,labels=False) if s.notna().sum()>=10 else np.nan)
dz=z.dropna(subset=['q'])
daily=dz[dz.q==4].groupby('date').exc.mean()-dz[dz.q==0].groupby('date').exc.mean()
daily=daily.dropna()*100
s=daily.sort_values(ascending=False)
print(f'  일별 스프레드 평균 {daily.mean():+.4f}%p  중앙 {daily.median():+.4f}  승률 {100*(daily>0).mean():.1f}%  ({len(daily)}일)')
for k in [1,3,5,10]:
    print(f'   상위 {k:2d}일 제거 후 평균 {s.iloc[k:].mean():+.4f}%p   (상위 {k}일 기여 {100*s.iloc[:k].sum()/max(daily.sum(),1e-9):.1f}%)')

print('\n'+'='*112); print('5. 대조군 — 날짜 내 신호 라벨 셔플 200회'); print('='*112)
rng=np.random.default_rng(11); null=[]
_d=d[['date','sig','exc']].copy(); _codes,_ = pd.factorize(_d.date)
_sig=_d.sig.values.copy(); _exc=_d.exc.values
_order=np.argsort(_codes,kind='stable'); _cs=_codes[_order]; _ss=_sig[_order]; _es=_exc[_order]
_bnd=np.flatnonzero(np.diff(_cs))+1; _grp=np.split(np.arange(len(_cs)),_bnd)
for _ in range(200):
    sh=np.empty_like(_ss)
    for ix in _grp: sh[ix]=rng.permutation(_ss[ix])
    qq=pd.qcut(pd.Series(sh).rank(method='first'),5,labels=False).values
    m=np.array([_es[qq==k].mean() for k in range(5)])*100
    null.append(m[-1]-m[0])
null=np.array(null)
print(f'  관측 {base:+.3f}%p   셔플 귀무 평균 {null.mean():+.3f} sd {null.std():.3f}   90%구간 [{np.percentile(null,5):+.3f}, {np.percentile(null,95):+.3f}]')
print(f'  경험적 p(셔플 >= 관측) = {np.mean(null>=base):.3f}')
