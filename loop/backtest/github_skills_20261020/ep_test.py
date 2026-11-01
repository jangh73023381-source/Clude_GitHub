"""Stockbee Episodic Pivot(가격·거래량 조건, ep_methodology.md): 갭/당일 ≥4% · 거래량 ≥3×20일평균 · 종가 위치 상단 · 저점까지 위험 관리 가능 · 과열 아님."""
import numpy as np, pandas as pd
from gh_stats import nw_se
Z=np.load('dense.npz'); dates=Z['dates'].astype(int); O,H,L,C,V=(Z[k] for k in 'OHLCV'); T,N=C.shape
cs=np.cumsum(np.nan_to_num(C*V),0); v20=np.full((T,N),np.nan); v20[20:]=(cs[20:]-cs[:-20])/20
LIQ=(C>=1000)&(v20>=1e9)
sh=lambda A,k=1: np.vstack([np.full((k,N),np.nan),A[:-k]])
with np.errstate(invalid='ignore',divide='ignore'):
    Cp=sh(C); gap=O/Cp-1; day=C/Cp-1
    av20=sh(pd.DataFrame(V).rolling(20).mean().values)
    vr=V/av20; cl=(C-L)/(H-L); risk=C/L-1
    pre20=Cp/sh(C,21)-1; pre60=Cp/sh(C,61)-1
    hi250=pd.DataFrame(H).rolling(250,min_periods=200).max().values
base=LIQ&((gap>=.04)|(day>=.04))&(vr>=3)
V_={'EP 기본 (≥4%·거래량3배·종가위치≥70%·저점까지≤8%)':base&(cl>=.7)&(risk<=.08),
    'EP + 과열 아님 (직전 20일 < +20%)':base&(cl>=.7)&(risk<=.08)&(pre20<.2),
    'EP + 소외/베이스 (직전 60일 −20%~+20%)':base&(cl>=.7)&(risk<=.08)&(np.abs(pre60)<=.2),
    'EP + 갭 ≥8% (강한 재평가)':LIQ&(gap>=.08)&(vr>=3)&(cl>=.7),
    'EP + 52주 신고가 돌파':base&(cl>=.7)&(C>=sh(hi250))}
rows=[]
for h in (5,20,60):
    F=np.vstack([C[h:]/C[:-h]-1,np.full((h,N),np.nan)])*100
    um={t:np.nanmean(np.where(LIQ[t],F[t],np.nan)) for t in range(260,T-h)}
    for nm,M in V_.items():
        tt,jj=np.where(M[260:T-h]); tt=tt+260
        r=F[tt,jj]; ok=np.isfinite(r); tt,jj,r=tt[ok],jj[ok],r[ok]
        ex=r-np.array([um[t] for t in tt])
        d=pd.DataFrame({'t':tt,'ex':ex}).groupby('t').ex.mean(); x=d.values; n=len(x); k=n//3; s=np.sort(x)[::-1]
        rows.append(dict(규칙=nm,보유=h,건수=len(r),신호일=n,초과=x.mean(),t=x.mean()/nw_se(x,min(h-1,20)),건별중앙=np.median(ex),승률=(r>0).mean()*100,
                         fold=f'{x[:k].mean():.2f}/{x[k:2*k].mean():.2f}/{x[2*k:].mean():.2f}',상위5pct제거=s[max(2,int(n*.05)):].mean()))
o=pd.DataFrame(rows); pd.set_option('display.width',250); pd.set_option('display.max_columns',20)
print(o.round(2).to_string(index=False)); o.to_csv('ep_test.csv',index=False)
