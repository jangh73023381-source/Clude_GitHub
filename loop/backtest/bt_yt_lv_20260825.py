#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_yt_lv_20260825.py — Rule NHI 를 **현행 확정 선정기(Rule LV v2.9)** 위에 얹었을 때의 증분.
   LV = mom20+RuleH 상위 pool30 → 최근 20거래일 실현변동성 하위 5종."""
import csv,os,sys,math,statistics,random
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__))
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
def picks(d,near_th=None,lv=True):
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
print('=== Rule LV(현행 확정) 대비 신고가근접·게이트 증분 — 7년 ETF 패널 ===\n',flush=True)
rep(run(None,False,False),'MOM  (mom20+RuleH)')
rep(run(None,True ,False),'LV   (현행 확정 v2.9)')
rep(run(None,True ,True ),'LV + 게이트')
rep(run(0.95,True ,False),'LV + 신고가0.95')
rep(run(0.95,True ,True ),'LV + 신고가0.95 + 게이트  ★')
rep(run(0.97,True ,True ),'LV + 신고가0.97 + 게이트')
rep(run(0.95,False,True ),'MOM + 신고가0.95 + 게이트')
# 전기간 복리 (게이트 OFF = 현금)
lv=run(None,True,False); nhi={d:p for d,p,*_ in run(0.95,True,True)}
sp=[];sl=[];sb=[]
for d,p,b,*_ in lv:
    sl.append(p); sb.append(b); sp.append(nhi.get(d,0.0))
cp,cl_,cb=cum(sp),cum(sl),cum(sb); yrs=len(sp)/252
print(f'\n[전기간 복리 · 게이트OFF일 현금 0%]  일수 {len(sl)}, 투자일 {len(nhi)} ({len(nhi)/len(sl)*100:.0f}%)',flush=True)
print(f'  LV+신고가+게이트 누적 {(cp[-1]-1)*100:+9.1f}% CAGR {(cp[-1]**(1/yrs)-1)*100:+6.1f}% MDD {mdd(cp):6.1f}%',flush=True)
print(f'  LV (현행)        누적 {(cl_[-1]-1)*100:+9.1f}% CAGR {(cl_[-1]**(1/yrs)-1)*100:+6.1f}% MDD {mdd(cl_):6.1f}%',flush=True)
print(f'  KODEX200        누적 {(cb[-1]-1)*100:+9.1f}% CAGR {(cb[-1]**(1/yrs)-1)*100:+6.1f}% MDD {mdd(cb):6.1f}%',flush=True)
