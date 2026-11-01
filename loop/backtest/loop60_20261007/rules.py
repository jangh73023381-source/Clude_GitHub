# -*- coding: utf-8 -*-
"""60거래일 한정 루프(2026-10-07) — 가능성 있었던 10축. 기준 Rule LV. 규칙 정의는 패널 무관(E 만 받는다)."""
import os,sys,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
os.chdir(os.path.join(BT,'loop10_20260926'))
from engine import load,Engine,prof,tstat,r5,folds
CASH='CASH'
def lag(X,k): return np.vstack([np.full((k,X.shape[1]),np.nan),X[:-k]])
def build(E):
    C,H=E.C,E.P['high']; bi=E.bi
    s20=E.vol(20); s5=E.vol(5)
    ma20=pd.Series(C[:,bi]).rolling(20).mean().values; ma60=pd.Series(C[:,bi]).rolling(60).mean().values
    hi250=pd.DataFrame(H).rolling(250,min_periods=200).max().values
    R=lambda k:(C/lag(C,k)-1)
    RS=0.4*R(63)+0.2*R(126)+0.2*R(189)+0.2*R(252)
    m5=R(5)*100; sk1=(lag(C,1)/lag(C,21)-1)*100
    def rk(M):  # 행별 백분위
        return pd.DataFrame(M).rank(axis=1,pct=True).values
    skb=0.8*rk(E.mom)+0.2*rk(sk1)
    lv=lambda i,pl:E.sel_lv(i,pl)
    def mix(i,pl):
        a=list(E.sel_lv(i,pl,n=3)); 
        for c in pl:
            if len(a)>=5: break
            if c not in a: a.append(c)
        return np.array(a)
    def sw(ma):
        return lambda i,pl: pl[:5] if C[i,bi]>ma[i] else E.sel_lv(i,pl)
    def vcp(i,pl):
        c=E.sel_lv(i,pl,n=8); v=(s5/s20)[i,c]; ok=~np.isnan(v)
        return c[ok][np.argsort(v[ok],kind='stable')[:5]] if ok.sum()>=5 else c[:5]
    def skiplow(i,pl):
        return E.sel_lv(i,pl,n=7)[2:7]
    def rs(i,pl): return E.pool(i,n=5,score=RS)
    def nhi(i,pl):
        if not C[i,bi]>ma20[i]: return CASH
        near=pl[C[i,pl]>=hi250[i,pl]*0.95]
        if len(near)==0: return CASH
        return E.sel_lv(i,near) if len(near)>=5 else near
    def sk(i,pl): return E.sel_lv(i,E.pool(i,n=30,score=skb))
    def mom5p(i,pl): return E.sel_lv(i,E.pool(i,n=30,score=m5))
    def cheap(i,pl):
        c=E.sel_lv(i,pl,n=10); v=C[i,c]; return c[np.argsort(v,kind='stable')[:5]]
    return {'LV(기준)':lv,
            '1 MOM(mom20 상위5)':lambda i,pl:pl[:5],
            '2 혼합 LV3+MOM2':mix,
            '3 국면전환 MA20(위=MOM/아래=LV)':sw(ma20),
            '3b 국면전환 MA60':sw(ma60),
            '4 변동성수축 σ하위8→σ5/σ20':vcp,
            '5 최저σ 2종 제외(σ순위3~7)':skiplow,
            '6 RS(IBD) 상위5':rs,
            '7 NHI(250일고가95%∩지수>MA20)':nhi,
            '8 SK1w 블렌드 pool→σ5':sk,
            '9 mom5 pool→σ5':mom5p,
            '10 저가 σ하위10→저가5':cheap}
def run(E,sel,idx):
    rows=[]; C=E.C
    for i in idx:
        pl=E.pool(i)
        if len(pl)<5: continue
        pk=sel(i,pl)
        univ=np.where((C[i]>=10000)&~np.isnan(E.fA[i]))[0]
        thr=np.nanquantile(E.fA[i,univ],0.9) if len(univ) else np.nan
        if isinstance(pk,str):
            a=o=0.0; hit=np.nan; n=0
        else:
            pk=np.asarray(pk); a=np.nanmean(E.fA[i,pk]); o=np.nanmean(E.fOO[i,pk]) if (~np.isnan(E.fOO[i,pk])).any() else np.nan
            hit=float(np.sum(E.fA[i,pk]>=thr)); n=len(pk)
        rows.append(dict(i=i,date=E.dates[i],A=a,OO=o,hit=hit,n=n,bA=E.fA[i,E.bi],bOO=E.fOO[i,E.bi]))
    return pd.DataFrame(rows)
