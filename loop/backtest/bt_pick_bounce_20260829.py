#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""추천 ETF 중 '보유일에 하락한 종목'이 다음날 오르는가 (7년 패널).
   선정일 d(정보컷) → 보유일 n=d+1 (여기서 매매·채점) → 익일 n2=d+2 를 본다."""
import csv,os,sys,math,statistics as st,random
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
    if c<=0 or o<=0: continue
    px[x['code']][x['date']]=(o,h,l,c,v); nm[x['code']]=x['name']
dates=sorted({d for c in px for d in px[c]})
ser={c:sorted(px[c]) for c in px}
ELIG=[c for c in px if eligible(nm.get(c,''))]
M={};SIG={}
for c in ELIG:
    s=ser[c]; cl=[px[c][d][3] for d in s]
    m={};sg={}
    for i in range(len(s)):
        if i>=MOM and cl[i-1]>0 and cl[i-3]>0:
            if not ((cl[i]/cl[i-1]-1)*100>10 or (cl[i]/cl[i-3]-1)*100>20):
                m[s[i]]=(cl[i]/cl[i-MOM]-1)*100
        if i>=LB:
            r=[(cl[j]/cl[j-1]-1)*100 for j in range(i-LB+1,i+1)]
            sg[s[i]]=st.stdev(r)
    M[c]=m;SIG[c]=sg
def picks(d,lv=True):
    lst=sorted(((M[c][d],c) for c in ELIG if d in M[c]),reverse=True)
    if not lst: return []
    if not lv: return [c for _,c in lst[:NPICK]]
    pool=[c for _,c in lst[:POOL]]
    sg=sorted((SIG[c][d],c) for c in pool if d in SIG[c])
    return pool[:NPICK] if len(sg)<NPICK else [c for _,c in sg[:NPICK]]

def build(lv=True):
    """각 (선정일 d, 픽 c) 마다 보유일 수익 r1, 익일 r2(및 갭·집행 분해)"""
    out=[]
    for i in range(len(dates)-2):
        d,n,n2=dates[i],dates[i+1],dates[i+2]
        if not all(x in px[BENCH] for x in (d,n,n2)): continue
        b_d,b_n,b_n2=px[BENCH][d],px[BENCH][n],px[BENCH][n2]
        b1=(b_n[3]/b_d[3]-1)*100
        b2=(b_n2[3]/b_n[3]-1)*100
        b2g=(b_n2[0]/b_n[3]-1)*100; b2e=(b_n2[3]/b_n2[0]-1)*100
        for c in picks(d,lv):
            if not all(x in px[c] for x in (d,n,n2)): continue
            p_d,p_n,p_n2=px[c][d],px[c][n],px[c][n2]
            r1=(p_n[3]/p_d[3]-1)*100
            r2=(p_n2[3]/p_n[3]-1)*100
            g2=(p_n2[0]/p_n[3]-1)*100; e2=(p_n2[3]/p_n2[0]-1)*100
            out.append(dict(d=d,n=n,code=c,r1=r1,r2=r2,g2=g2,e2=e2,
                            b1=b1,b2=b2,b2g=b2g,b2e=b2e,ex1=r1-b1,ex2=r2-b2,
                            exg=g2-b2g,exe=e2-b2e))
    return out

def boot(byday,seed=7,n=1500):
    dm=[st.mean(v) for v in byday.values()]
    rnd=random.Random(seed); bs=[]
    k=len(dm)
    for _ in range(n):
        bs.append(sum(rnd.choice(dm) for _ in range(k))/k)
    bs.sort(); return bs[int(n*0.025)],bs[int(n*0.975)]

def rep(rows,key,label,bench_key=None):
    if len(rows)<20: print(f"{label:38s} n={len(rows)}"); return
    v=[r[key] for r in rows]
    byd=defaultdict(list)
    for r in rows: byd[r['n']].append(r[key])
    lo,hi=boot(byd)
    m=st.mean(v)
    print(f"{label:38s} n={len(v):5d} 날짜 {len(byd):4d} | 평균 {m:+6.3f}% [{lo:+.3f},{hi:+.3f}] "
          f"| 중앙 {st.median(v):+6.3f}% | 승률 {sum(1 for x in v if x>0)/len(v)*100:4.1f}%")

for LVMODE,LBL in ((True,"Rule LV (현행 확정)"),(False,"MOM20 (종전)")):
    A=build(LVMODE)
    print("="*118)
    print(f"[{LBL}] 픽-일 {len(A)}건 · {A[0]['n']}~{A[-1]['n']}")
    dn=[r for r in A if r['r1']<0]; up=[r for r in A if r['r1']>0]
    print(f"  보유일 하락 픽 {len(dn)}건({len(dn)/len(A)*100:.1f}%) · 상승 {len(up)}건")
    print("\n  ■ 익일 절대수익률 r2")
    rep(A,'r2',"    전체 픽")
    rep(dn,'r2',"    보유일 하락 픽")
    rep(up,'r2',"    보유일 상승 픽")
    print("\n  ■ 익일 KODEX200 대비 초과 ex2")
    rep(A,'ex2',"    전체 픽")
    rep(dn,'ex2',"    보유일 하락 픽")
    rep(up,'ex2',"    보유일 상승 픽")
    print("\n  ■ 하락 픽의 익일 초과를 갭/집행으로 분해")
    rep(dn,'exg',"    갭(익일시가/당일종가)")
    rep(dn,'exe',"    집행(익일종가/익일시가)")
