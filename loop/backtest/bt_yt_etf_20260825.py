#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_yt_etf_20260825.py — 유튜브 종목선정 규칙(신고가 근접 축)의 **ETF 트랙** 검정.

배경: 2026-08-25 유튜브 3편(대왕개미 홍인기 '매수 전 체크 8가지' / 더트레이딩tv '주도테마
대장주' / 주식당 '단기 종목선정 3기준')에서 일봉으로 구현 가능한 축을 뽑아 단일종목 7년
패널에서 검정한 결과, **살아남은 축은 '신고가 근접' 하나**였다. 그 축을 확정방법(mom20+RuleH)
위에 얹어 ETF 유니버스에서도 재현되는지 본다.

지표: A 종가(D)→종가(D+1) · G 갭 · B 집행(시가→종가) — CLAUDE.md §4 / metric_abg 관례.
비용 0 (v2.8). 벤치 069500.
"""
import csv, os, sys, math, statistics
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(os.path.dirname(HERE),'references','scripts'))
from universe_filters import eligible

LONG=os.path.join(HERE,'panel_ohlc_long.csv')
BENCH,NPICK,MOM='069500',5,20

def load():
    px=defaultdict(dict); nm={}
    r=csv.DictReader(open(LONG,encoding='utf-8'))
    for x in r:
        try: o,h,l,c,v=float(x['open']),float(x['high']),float(x['low']),float(x['close']),float(x['volume'])
        except ValueError: continue
        if c<=0: continue
        px[x['code']][x['date']]=(o,h,l,c,v); nm[x['code']]=x['name']
    return px,nm

def cum(rs):
    x=1.0;o=[]
    for r in rs: x*=(1+r/100); o.append(x)
    return o
def mdd(cv):
    pk=cv[0];w=0.0
    for x in cv: pk=max(pk,x); w=min(w,x/pk-1)
    return w*100

px,nm=load()
dates=sorted({d for c in px for d in px[c]})
bcl=[px[BENCH][d][3] for d in dates if d in px[BENCH]]
bd=[d for d in dates if d in px[BENCH]]
gate={}
for i,d in enumerate(bd):
    gate[d]= i>=20 and bcl[i]>sum(bcl[i-19:i+1])/20

# 후보 산출: mom20 + Rule H(과열 컷) + 신고가근접(선택)
def build(near_th=None, lookback=250):
    out={}
    for i,d in enumerate(dates):
        if i<max(MOM,60): continue
        lst=[]
        for c in px:
            if not eligible(nm.get(c,'')): continue
            a=px[c].get(dates[i-MOM]); b=px[c].get(d)
            if not (a and b): continue
            c1=px[c].get(dates[i-1]); c3=px[c].get(dates[i-3])
            if c1 and c3 and ((b[3]/c1[3]-1)*100>10 or (b[3]/c3[3]-1)*100>20): continue   # Rule H
            if near_th is not None:
                hs=[px[c][dates[j]][1] for j in range(max(0,i-lookback+1),i+1) if dates[j] in px[c]]
                if len(hs)<60: continue
                hh=max(hs)
                if hh<=0 or b[3]/hh<near_th: continue
            lst.append(((b[3]/a[3]-1)*100,c))
        lst.sort(reverse=True)
        out[d]=lst
    return out

def score(cands,need_gate=False,npick=NPICK,label=''):
    rows=[]
    for i,d in enumerate(dates[:-1]):
        n=dates[i+1]
        if need_gate and not gate.get(d): continue
        if d not in px[BENCH] or n not in px[BENCH]: continue
        bd0,bd1=px[BENCH][d],px[BENCH][n]
        bA=(bd1[3]/bd0[3]-1)*100; bG=(bd1[0]/bd0[3]-1)*100; bB=(bd1[3]/bd1[0]-1)*100
        cd=cands.get(d)
        if not cd or len(cd)<npick: continue
        A=[];G=[];B=[]
        for _,c in cd[:npick]:
            a=px[c].get(d); b=px[c].get(n)
            if not a or not b or a[3]<=0 or b[0]<=0: continue
            A.append((b[3]/a[3]-1)*100); G.append((b[0]/a[3]-1)*100); B.append((b[3]/b[0]-1)*100)
        if len(A)<npick: continue
        rows.append((d,sum(A)/npick,bA,sum(G)/npick,bG,sum(B)/npick,bB))
    N=len(rows)
    if N<50: print(f'{label}: N부족 {N}'); return None
    eA=[r[1]-r[2] for r in rows]; eG=[r[3]-r[4] for r in rows]; eB=[r[5]-r[6] for r in rows]
    def st(e):
        m=statistics.mean(e); return m, m/(statistics.stdev(e)/math.sqrt(N)), sum(1 for x in e if x>0)/N*100
    mA,tA,wA=st(eA); mG,tG,_=st(eG); mB,tB,_=st(eB)
    cp=cum([r[1] for r in rows]); cb=cum([r[2] for r in rows]); yrs=N/252
    k=N//3
    fold=[statistics.mean(eA[j*k:(j+1)*k] if j<2 else eA[2*k:]) for j in range(3)]
    s=sorted(eA,reverse=True); tot=sum(eA)
    print(f'{label:<30s} N={N:4d} A{mA:+.4f} t{tA:+5.2f} 승{wA:4.1f}% | '
          f'CAGR{(cp[-1]**(1/yrs)-1)*100:+6.1f}%(벤{(cb[-1]**(1/yrs)-1)*100:+.1f}%) MDD{mdd(cp):6.1f}% '
          f'Sh{statistics.mean([r[1] for r in rows])/statistics.stdev([r[1] for r in rows])*math.sqrt(252):4.2f}')
    print(f'{"":30s}   G{mG:+.4f}(t{tG:+.2f}, 갭비중{mG/mA*100 if mA else 0:5.1f}%) '
          f'B{mB:+.4f}(t{tB:+.2f}) | fold {[f"{x:+.4f}" for x in fold]} | '
          f'-상위3일 {(tot-sum(s[:3]))/(N-3):+.4f} 중앙 {statistics.median(eA):+.4f}')
    return rows

print('=== ETF 트랙 · 7년 패널 · 신고가근접 축 검정 (무비용, KODEX200 대비) ===\n')
base=build(None)
score(base,False,label='baseline mom20+RuleH')
score(base,True, label='baseline + 지수게이트')
for th in (0.90,0.93,0.95,0.97):
    c=build(th)
    score(c,False,label=f'+신고가근접 {th:.2f}')
    score(c,True, label=f'+신고가근접 {th:.2f} +게이트')
