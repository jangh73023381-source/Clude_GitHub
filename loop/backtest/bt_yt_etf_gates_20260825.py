#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_yt_etf_gates_20260825.py — Rule NHI(신고가근접 × 지수 MA20 게이트) 승격 관문 R1·R3·R4·R5.
   2026-08-25 유튜브 종목선정 규칙 검정. 무비용(v2.8), 벤치 069500, 7년 패널."""
import csv,os,sys,math,statistics,random
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(os.path.dirname(HERE),'references','scripts'))
from universe_filters import eligible
LONG=os.path.join(HERE,'panel_ohlc_long.csv'); BENCH,NPICK,MOM='069500',5,20
px=defaultdict(dict); nm={}
for x in csv.DictReader(open(LONG,encoding='utf-8')):
    try: o,h,l,c,v=float(x['open']),float(x['high']),float(x['low']),float(x['close']),float(x['volume'])
    except ValueError: continue
    if c<=0: continue
    px[x['code']][x['date']]=(o,h,l,c,v); nm[x['code']]=x['name']
dates=sorted({d for c in px for d in px[c]})
bd=[d for d in dates if d in px[BENCH]]; bcl=[px[BENCH][d][3] for d in bd]
def mk_gate(w):
    return {d:(i>=w and bcl[i]>sum(bcl[i-w+1:i+1])/w) for i,d in enumerate(bd)}
def cum(rs):
    x=1.0;o=[]
    for r in rs: x*=(1+r/100); o.append(x)
    return o
def mdd(cv):
    pk=cv[0];w=0.0
    for x in cv: pk=max(pk,x); w=min(w,x/pk-1)
    return w*100
# --- 종목별 사전계산: mom20 / RuleH / near(lookback,ref) ---
ser={c:sorted(px[c]) for c in px}
NEAR={}   # (lb,ref) -> code -> date -> ratio
def prep_near(lb,ref):
    key=(lb,ref)
    if key in NEAR: return NEAR[key]
    out={}
    for c,s in ser.items():
        arr=[px[c][d][1 if ref=='high' else 3] for d in s]
        cl=[px[c][d][3] for d in s]; f={}
        for i in range(len(s)):
            if i<59: continue
            hh=max(arr[max(0,i-lb+1):i+1])
            if hh>0: f[s[i]]=cl[i]/hh
        out[c]=f
    NEAR[key]=out; return out
BASE={}
for c,s in ser.items():
    cl=[px[c][d][3] for d in s]; f={}
    for i in range(len(s)):
        if i<MOM: continue
        if cl[i-1]>0 and cl[i-3]>0 and ((cl[i]/cl[i-1]-1)*100>10 or (cl[i]/cl[i-3]-1)*100>20): continue  # Rule H
        f[s[i]]=(cl[i]/cl[i-MOM]-1)*100
    BASE[c]=f
ELIG=[c for c in px if eligible(nm.get(c,''))]

def cands(near_th=None,lb=250,ref='high'):
    nr=prep_near(lb,ref) if near_th is not None else None
    out={}
    for d in dates:
        lst=[]
        for c in ELIG:
            m=BASE[c].get(d)
            if m is None: continue
            if nr is not None:
                r=nr[c].get(d)
                if r is None or r<near_th: continue
            lst.append((m,c))
        lst.sort(reverse=True); out[d]=lst
    return out

def score(cd,gate=None,npick=NPICK,seed=None,rows_only=False):
    rng=random.Random(seed); rows=[]
    for i,d in enumerate(dates[:-1]):
        n=dates[i+1]
        if gate is not None and not gate.get(d): continue
        if d not in px[BENCH] or n not in px[BENCH]: continue
        bA=(px[BENCH][n][3]/px[BENCH][d][3]-1)*100
        lst=cd.get(d)
        if not lst or len(lst)<npick: continue
        pick=[c for _,c in lst]
        if seed is not None: pick=pick[:]; rng.shuffle(pick)
        A=[]
        for c in pick[:npick]:
            a=px[c].get(d); b=px[c].get(n)
            if not a or not b or a[3]<=0: continue
            A.append((b[3]/a[3]-1)*100)
        if len(A)<npick: continue
        rows.append((d,sum(A)/npick,bA))
    if rows_only: return rows
    N=len(rows)
    if N<50: return None
    ex=[r[1]-r[2] for r in rows]; m=statistics.mean(ex)
    return dict(N=N,m=m,t=m/(statistics.stdev(ex)/math.sqrt(N)),rows=rows,ex=ex)

g20=mk_gate(20); c95=cands(0.95); cnone=cands(None)
print('=== R1 파라미터 고원 — 두 축을 각각 본다 ===',flush=True)
print('[축1 게이트 룩백] (신고가근접 0.95 고정)',flush=True)
for w in (10,20,40,60,120):
    s=score(c95,mk_gate(w)); print(f'  MA{w:3d}: N={s["N"]:4d} 초과 {s["m"]:+.4f} t={s["t"]:+.2f}',flush=True)
print('[축2 신고가 룩백] (MA20 게이트 고정)',flush=True)
for lb in (60,120,250,500):
    s=score(cands(0.95,lb),g20); print(f'  {lb:3d}일: N={s["N"]:4d} 초과 {s["m"]:+.4f} t={s["t"]:+.2f}',flush=True)
print('[R3 정의교체 — 최고"가" 대신 최고"종가" 기준]',flush=True)
for lb in (120,250):
    s=score(cands(0.95,lb,'close'),g20); print(f'  종가기준 {lb}일: N={s["N"]:4d} 초과 {s["m"]:+.4f} t={s["t"]:+.2f}',flush=True)
print('\n=== R4 플라시보 — 같은 pool 내 무작위 5종 200회 ===',flush=True)
base=score(c95,g20); ms=sorted(score(c95,g20,seed=7000+k)['m'] for k in range(200))
print(f'  무작위 5%={ms[10]:+.4f} 중앙={ms[100]:+.4f} 95%={ms[190]:+.4f}',flush=True)
print(f'  mom20 정렬 = {base["m"]:+.4f} → p={sum(1 for x in ms if x>=base["m"])/200:.3f}',flush=True)
print('\n=== 2x2 상호작용 ===',flush=True)
for lb,cd,g in [('baseline',cnone,None),('baseline+게이트',cnone,g20),('신고가만',c95,None),('신고가+게이트',c95,g20)]:
    s=score(cd,g); print(f'  {lb:<16s} N={s["N"]:4d} 초과 {s["m"]:+.4f} t={s["t"]:+.2f}',flush=True)
print('\n=== 전기간 복리 (게이트 OFF 일은 현금 0%) ===',flush=True)
rb=score(cnone,None,rows_only=True); rn={d:p for d,p,b in score(c95,g20,rows_only=True)}
sp=[];sb=[];sl=[]
for d,p,b in rb:
    sl.append(p); sb.append(b); sp.append(rn.get(d,0.0))
cp,cb,cl_=cum(sp),cum(sb),cum(sl); yrs=len(sp)/252
print(f'  Rule NHI(게이트일만)  누적 {(cp[-1]-1)*100:+9.1f}% CAGR {(cp[-1]**(1/yrs)-1)*100:+6.1f}% MDD {mdd(cp):6.1f}%',flush=True)
print(f'  baseline(매일)       누적 {(cl_[-1]-1)*100:+9.1f}% CAGR {(cl_[-1]**(1/yrs)-1)*100:+6.1f}% MDD {mdd(cl_):6.1f}%',flush=True)
print(f'  KODEX200            누적 {(cb[-1]-1)*100:+9.1f}% CAGR {(cb[-1]**(1/yrs)-1)*100:+6.1f}% MDD {mdd(cb):6.1f}%',flush=True)
print(f'  투자일수 {len(rn)}/{len(rb)} ({len(rn)/len(rb)*100:.0f}%)',flush=True)
print('\n=== 연도별 (게이트일 한정) ===',flush=True)
yb=defaultdict(list)
for d,p,b in score(c95,g20,rows_only=True): yb[d[:4]].append(p-b)
for y in sorted(yb):
    v=yb[y]; print(f'  {y} N={len(v):4d} 초과 {statistics.mean(v):+.4f} 승률 {sum(1 for x in v if x>0)/len(v)*100:4.1f}%',flush=True)
