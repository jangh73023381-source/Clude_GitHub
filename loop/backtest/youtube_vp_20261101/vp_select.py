#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_yt_lv_20260825.py — Rule NHI 를 **현행 확정 선정기(Rule LV v2.9)** 위에 얹었을 때의 증분.
   LV = mom20+RuleH 상위 pool30 → 최근 20거래일 실현변동성 하위 5종."""
import csv,os,sys,math,statistics,random
from collections import defaultdict
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(os.path.dirname(HERE),'references','scripts'))
from universe_filters import eligible
LONG=os.path.join(HERE,'panel_ohlc_long.csv'); BENCH,NPICK,MOM='069500',5,20
POOL,LB=30,20
px=defaultdict(dict); nm={}
for x in csv.DictReader(open(LONG,encoding='utf-8')):
    try: o,h,l,c,v=float(x['open']),float(x['high']),float(x['low']),float(x['close']),float(x['volume'])
    except ValueError: continue
    if c<=0: continue
    px[x['code']][x['date']]=(o,h,l,c,v); nm[x['code']]=x['name']
dates=sorted({d for c in px for d in px[c]})
bd=[d for d in dates if d in px[BENCH]]; bcl=[px[BENCH][d][3] for d in bd]
gate={d:(i>=20 and bcl[i]>sum(bcl[i-19:i+1])/20) for i,d in enumerate(bd)}
ser={c:sorted(px[c]) for c in px}
ELIG=[c for c in px if eligible(nm.get(c,''))]
M={};SIG={};NR={}
for c in ELIG:
    s=ser[c]; cl=[px[c][d][3] for d in s]; hi=[px[c][d][1] for d in s]
    m={};sg={};nr={}
    for i in range(len(s)):
        if i>=MOM and cl[i-1]>0 and cl[i-3]>0:
            if not ((cl[i]/cl[i-1]-1)*100>10 or (cl[i]/cl[i-3]-1)*100>20):
                m[s[i]]=(cl[i]/cl[i-MOM]-1)*100
        if i>=LB:
            r=[(cl[j]/cl[j-1]-1)*100 for j in range(i-LB+1,i+1)]
            sg[s[i]]=statistics.stdev(r)
        if i>=59:
            hh=max(hi[max(0,i-249):i+1])
            if hh>0: nr[s[i]]=cl[i]/hh
    M[c]=m;SIG[c]=sg;NR[c]=nr
def cum(rs):
    x=1.0;o=[]
    for r in rs: x*=(1+r/100); o.append(x)
    return o
def mdd(cv):
    pk=cv[0];w=0.0
    for x in cv: pk=max(pk,x); w=min(w,x/pk-1)
    return w*100
def picks_OLD(d,near_th=None,lv=True):
    lst=[]
    for c in ELIG:
        v=M[c].get(d)
        if v is None: continue
        if near_th is not None:
            r=NR[c].get(d)
            if r is None or r<near_th: continue
        lst.append((v,c))
    lst.sort(reverse=True)
    if not lv: return [c for _,c in lst[:NPICK]]
    pool=[c for _,c in lst[:POOL]]
    sg=[(SIG[c].get(d),c) for c in pool if SIG[c].get(d) is not None]
    if len(sg)<NPICK: return pool[:NPICK]
    sg.sort()
    return [c for _,c in sg[:NPICK]]
def run(near_th,lv,use_gate):
    rows=[]
    for i,d in enumerate(dates[:-1]):
        n=dates[i+1]
        if use_gate and not gate.get(d): continue
        if d not in px[BENCH] or n not in px[BENCH]: continue
        b0,b1=px[BENCH][d],px[BENCH][n]
        bA=(b1[3]/b0[3]-1)*100; bG=(b1[0]/b0[3]-1)*100; bB=(b1[3]/b1[0]-1)*100
        sel=picks(d,near_th,lv)
        if len(sel)<NPICK: continue
        A=[];G=[];B=[]
        for c in sel:
            a=px[c].get(d); b=px[c].get(n)
            if not a or not b or a[3]<=0 or b[0]<=0: continue
            A.append((b[3]/a[3]-1)*100); G.append((b[0]/a[3]-1)*100); B.append((b[3]/b[0]-1)*100)
        if len(A)<NPICK: continue
        rows.append((d,sum(A)/NPICK,bA,sum(G)/NPICK,bG,sum(B)/NPICK,bB))
    return rows
def rep(rows,label,full_days=None):
    N=len(rows); eA=[r[1]-r[2] for r in rows]; eB=[r[5]-r[6] for r in rows]; eG=[r[3]-r[4] for r in rows]
    m=statistics.mean(eA); t=m/(statistics.stdev(eA)/math.sqrt(N))
    mB=statistics.mean(eB); tB=mB/(statistics.stdev(eB)/math.sqrt(N))
    mG=statistics.mean(eG)
    cp=cum([r[1] for r in rows]); yrs=N/252
    k=N//3; fold=[statistics.mean(eA[j*k:(j+1)*k] if j<2 else eA[2*k:]) for j in range(3)]
    s=sorted(eA,reverse=True); tot=sum(eA)
    print(f'{label:<34s} N={N:4d} A{m:+.4f} t{t:+5.2f} | 갭{mG/m*100 if m else 0:5.1f}% B{mB:+.4f}(t{tB:+.2f}) | '
          f'CAGR{(cp[-1]**(1/yrs)-1)*100:+6.1f}% MDD{mdd(cp):6.1f}% Sh{statistics.mean([r[1] for r in rows])/statistics.stdev([r[1] for r in rows])*math.sqrt(252):4.2f} | '
          f'fold{[f"{x:+.3f}" for x in fold]} -3일{(tot-sum(s[:3]))/(N-3):+.4f} 중앙{statistics.median(eA):+.4f}',flush=True)
    return rows

import numpy as np
NB=40
def poc_series(c,N):
    s=ser[c]; H=np.array([px[c][d][1] for d in s]); L=np.array([px[c][d][2] for d in s]); V=np.array([px[c][d][4] for d in s])
    out={}
    for i in range(N-1,len(s)):
        h,l,v=H[i-N+1:i+1],L[i-N+1:i+1],V[i-N+1:i+1]
        if v.sum()<=0: continue
        lo,hi=l.min(),h.max(); w=(hi-lo)/NB
        if w<=0: continue
        e=lo+w*np.arange(NB+1); rg=np.maximum(h-l,1e-9)[:,None]
        ov=np.clip(np.minimum(h[:,None],e[None,1:])-np.maximum(l[:,None],e[None,:-1]),0,None)/rg
        z=(h-l)<1e-9
        if z.any(): ov[z]=((l[z,None]>=e[None,:-1])&(l[z,None]<e[None,1:])).astype(float)
        out[s[i]]=lo+w*((ov*v[:,None]).sum(0).argmax()+0.5)
    return out
MA={}
for c in ELIG:
    s=ser[c]; cl=[px[c][d][3] for d in s]; MA[c]={}
    for i in range(59,len(s)): MA[c][s[i]]=(sum(cl[i-19:i+1])/20,sum(cl[i-59:i+1])/60)
POC={N:{c:poc_series(c,N) for c in ELIG} for N in (20,60)}
def flag(c,d,kind):
    C=px[c][d][3]
    if kind=='POC20': p=POC[20][c].get(d); return None if p is None else C>p
    if kind=='POC60': p=POC[60][c].get(d); return None if p is None else C>p
    if kind=='MA20': m=MA[c].get(d); return None if m is None else C>m[0]
    if kind=='MA60': m=MA[c].get(d); return None if m is None else C>m[1]
RNG=random.Random(11); PERS={}
def picks(d,kind=None,where='pool',rand=None):
    lst=sorted([(M[c][d],c) for c in ELIG if d in M[c]],reverse=True)
    if kind and where=='univ': lst=[x for x in lst if flag(x[1],d,kind)]
    pool=[c for _,c in lst[:POOL]]
    if kind and where=='pool':
        keep=[c for c in pool if flag(c,d,kind)]
        if rand=='daily':
            k=len(keep); keep=RNG.sample(pool,k)
        elif rand=='pers':
            k=len(keep); keep=sorted(pool,key=lambda c:PERS[c])[:k]
        pool=keep
    sg=sorted([(SIG[c].get(d),c) for c in pool if SIG[c].get(d) is not None])
    if len(sg)<NPICK: return []
    return [c for _,c in sg[:NPICK]]
def run2(**kw):
    rows=[]
    for i,d in enumerate(dates[:-1]):
        n=dates[i+1]
        if d not in px[BENCH] or n not in px[BENCH]: continue
        b0,b1=px[BENCH][d],px[BENCH][n]
        bA=(b1[3]/b0[3]-1)*100; bG=(b1[0]/b0[3]-1)*100; bB=(b1[3]/b1[0]-1)*100
        sel=picks(d,**kw); A=[];G=[];B=[]
        if len(sel)<NPICK:   # 5종 미만이면 현금(LV 폴백 없음과 같은 처리 — 행은 유지)
            rows.append((d,0.0,bA,0.0,bG,0.0,bB)); continue
        for c in sel:
            a=px[c].get(d); b=px[c].get(n)
            if not a or not b: continue
            A.append((b[3]/a[3]-1)*100); G.append((b[0]/a[3]-1)*100); B.append((b[3]/b[0]-1)*100)
        if len(A)<NPICK: continue
        rows.append((d,sum(A)/NPICK,bA,sum(G)/NPICK,bG,sum(B)/NPICK,bB))
    return rows
def stats(rows):
    p=[r[1] for r in rows]; cp=cum(p); yrs=len(p)/252
    return (cp[-1]**(1/yrs)-1)*100, mdd(cp), statistics.mean(p)/statistics.stdev(p)*math.sqrt(252)
# 중첩도: pool30 중 POC 위 비율
ov={k:[] for k in ('POC20','POC60','MA20','MA60')}
for d in dates[60::5]:
    lst=sorted([(M[c][d],c) for c in ELIG if d in M[c]],reverse=True)[:POOL]
    for k in ov:
        f=[flag(c,d,k) for _,c in lst]; f=[x for x in f if x is not None]
        if f: ov[k].append(sum(f)/len(f))
print('pool30 중 조건 충족 비율(평균):',{k:round(statistics.mean(v)*100,1) for k,v in ov.items()},flush=True)
import itertools
base=run2(); rep(base,'LV (현행 v2.9)')
res={}
for kind in ('POC20','POC60','MA20','MA60'):
    for where in ('pool','univ'):
        r=run2(kind=kind,where=where); res[(kind,where)]=r; rep(r,f'LV + {kind} 위 [{where}]')
        cg,md,sh=stats(r); cb,mb,sb=stats(base)
        nd=[x for x in r if x[1]==0.0 and x[3]==0.0]
        print(f'      ΔCAGR {cg-cb:+.1f} ΔMDD {md-mb:+.1f} ΔSh {sh-sb:+.2f} | 현금일 {len(nd)}',flush=True)
# 무작위 대조 (pool 필터 버전만) — 같은 개수만 남기기
for kind in ('POC20','POC60'):
    real=stats(res[(kind,'pool')])
    for mode in ('daily','pers'):
        sims=[]
        for rep_i in range(40):
            PERS.clear(); PERS.update({c:RNG.random() for c in ELIG})
            sims.append(stats(run2(kind=kind,where='pool',rand=mode)))
        sims=np.array(sims)
        p_sh=(sims[:,2]>=real[2]).mean(); p_md=(sims[:,1]>=real[1]).mean(); p_cg=(sims[:,0]>=real[0]).mean()
        print(f'  무작위[{mode}] {kind}: 실제 CAGR {real[0]:+.1f} MDD {real[1]:.1f} Sh {real[2]:.2f} | 대조 평균 {sims[:,0].mean():+.1f}/{sims[:,1].mean():.1f}/{sims[:,2].mean():.2f} | p(CAGR) {p_cg:.3f} p(MDD) {p_md:.3f} p(Sh) {p_sh:.3f}',flush=True)
