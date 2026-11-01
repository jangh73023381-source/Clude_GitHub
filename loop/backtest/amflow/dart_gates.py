# -*- coding: utf-8 -*-
"""글로벌 운용사 대량보유 공시 → 이후 초과수익 검정. R1~R5 + 지속형 무작위 대조군."""
import os,sys
import numpy as np, pandas as pd
from math import erf,sqrt
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
S=os.path.join(BT,'sjh')
C=np.load(os.path.join(S,'C.npy')); dates=np.load(os.path.join(S,'dates.npy')); codes=np.load(os.path.join(S,'codes.npy'),allow_pickle=True)
codes=np.array([str(c).zfill(6) for c in codes])
di={int(d):i for i,d in enumerate(dates)}; ci={c:i for i,c in enumerate(codes)}
print(f'패널 {C.shape[0]}일 × {C.shape[1]}종  {dates[0]}~{dates[-1]}')
R=np.full_like(C,np.nan,dtype=float); R[1:]=C[1:]/C[:-1]-1
BEN=np.nanmean(R,axis=1)                       # 전종목 동일가중 벤치
def fwd(ti,ci_,k):
    a,b=ti,ti+k
    if b>=C.shape[0] or ti<0: return np.nan
    p0,p1=C[a,ci_],C[b,ci_]
    if not np.isfinite(p0) or not np.isfinite(p1) or p0<=0: return np.nan
    bm=np.nanprod(1+BEN[a+1:b+1])-1
    return (p1/p0-1)-bm
def tt1(x):
    x=np.asarray(x,float); x=x[np.isfinite(x)]
    if len(x)<5: return np.nan,np.nan,0
    t=x.mean()/max(x.std(ddof=1)/sqrt(len(x)),1e-12)
    return x.mean(), t, len(x)
def pv(t): return 2*(1-0.5*(1+erf(abs(t)/sqrt(2)))) if np.isfinite(t) else np.nan

fx=pd.read_csv('_dart_fx.csv',dtype=str)
m=pd.read_csv('_majorstock.csv',dtype=str)
m=m[m.rcept_no.notna()&(m.rcept_no.astype(str).str.strip()!='')]
j=fx.merge(m[['rcept_no','stkrt','stkrt_irds']],on='rcept_no',how='left')
j['dt']=j.rcept_dt.astype(int)
j['ti']=j.dt.map(lambda d: di.get(d, next((di[x] for x in sorted(di) if x>=d), -1)))
j['ci']=j.stock_code.map(ci)
j=j[(j.ti>=0)&j.ci.notna()].copy(); j['ci']=j.ci.astype(int)
print(f'공시 {len(fx):,}건 → 패널 매칭 {len(j):,}건 (종목 {j.ci.nunique()}개)')

print('\n'+'='*96); print('A. 7년 전체 — 공시 발생 이벤트 (방향 무관)'); print('='*96)
for k in [1,5,10,20,40]:
    v=[fwd(int(r.ti),int(r.ci),k) for r in j.itertuples()]
    mu,t,n=tt1(v); print(f'  D+{k:<3} 초과 {100*mu:+.3f}%  t={t:+.2f}  p={pv(t):.3f}  n={n}')

jj=j[j.stkrt_irds.notna()].copy(); jj['irds']=pd.to_numeric(jj.stkrt_irds,errors='coerce')
jj=jj[jj.irds.notna()]
print('\n'+'='*96); print(f'B. 2년(2024-09~) 방향별 — 보유비율 증감  n={len(jj)}'); print('='*96)
up=jj[jj.irds>0]; dn=jj[jj.irds<0]; fl=jj[jj.irds==0]
print(f'  증가 {len(up)}건 · 감소 {len(dn)}건 · 변동없음 {len(fl)}건')
for lbl,g in [('증가(+)',up),('감소(-)',dn)]:
    row=[]
    for k in [1,5,10,20,40]:
        mu,t,n=tt1([fwd(int(r.ti),int(r.ci),k) for r in g.itertuples()])
        row.append(f'D+{k}: {100*mu:+.2f}%(t={t:+.2f})')
    print(f'  {lbl:<8} '+'  '.join(row))
# 증가-감소 스프레드
for k in [5,20]:
    a=np.array([fwd(int(r.ti),int(r.ci),k) for r in up.itertuples()],float)
    b=np.array([fwd(int(r.ti),int(r.ci),k) for r in dn.itertuples()],float)
    a=a[np.isfinite(a)]; b=b[np.isfinite(b)]
    se=sqrt(a.var(ddof=1)/len(a)+b.var(ddof=1)/len(b)); t=(a.mean()-b.mean())/max(se,1e-12)
    print(f'  증가-감소 D+{k}: {100*(a.mean()-b.mean()):+.2f}%p  t={t:+.2f}  p={pv(t):.3f}')

print('\n'+'='*96); print('C. R2 — 연도 fold (7년 이벤트, D+20)'); print('='*96)
j['yr']=j.rcept_dt.str[:4]
for y in sorted(j.yr.unique()):
    g=j[j.yr==y]; mu,t,n=tt1([fwd(int(r.ti),int(r.ci),20) for r in g.itertuples()])
    print(f'  {y}: 초과 {100*mu:+.3f}%  t={t:+.2f}  n={n}')

print('\n'+'='*96); print('D. R5 — 꼬리 기여도 (7년 이벤트 D+20)'); print('='*96)
v=np.array([fwd(int(r.ti),int(r.ci),20) for r in j.itertuples()],float); v=v[np.isfinite(v)]
s=np.sort(v)[::-1]
print(f'  평균 {100*v.mean():+.3f}%  중앙 {100*np.median(v):+.3f}%  승률 {100*(v>0).mean():.1f}%  n={len(v)}')
for k in [1,3,5,10]:
    print(f'   상위 {k:2d}건 제거 후 평균 {100*s[k:].mean():+.3f}%   (상위 {k}건 기여 {100*s[:k].sum()/max(v.sum(),1e-9):.1f}%)')

print('\n'+'='*96); print('E. 대조군 — 같은 종목 무작위 날짜 300회 (지속형 대조군)'); print('='*96)
rng=np.random.default_rng(5); obs=v.mean(); null=[]
tis=j.ti.values; cis=j.ci.values; lo,hi=20,C.shape[0]-21
for _ in range(300):
    rt=rng.integers(lo,hi,size=len(cis))
    x=np.array([fwd(int(a),int(b),20) for a,b in zip(rt,cis)],float); x=x[np.isfinite(x)]
    null.append(x.mean())
null=np.array(null)
print(f'  관측 {100*obs:+.3f}%   귀무 평균 {100*null.mean():+.3f}% sd {100*null.std():.3f}')
print(f'  90% 구간 [{100*np.percentile(null,5):+.3f}, {100*np.percentile(null,95):+.3f}]   경험적 p(귀무>=관측) = {np.mean(null>=obs):.3f}')
