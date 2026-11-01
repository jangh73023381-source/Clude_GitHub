# -*- coding: utf-8 -*-
"""bt_abg_20260822.py — baseline·Rule LV 의 초과수익을 A·G·B 로 분해한다 (7년 패널).

  A 종가(D)→종가(D+1)   = 현행 1차 지표
  G 종가(D)→시가(D+1)   = 갭 — 선정 시각(T 06:00) 이후에 결정되는 부분
  B 시가(D+1)→종가(D+1) = 실제 집행 구간

묻는 것: **우리가 재는 초과수익 중 실제로 집행 가능한 몫은 얼마인가.**
사용자는 지정가(-1.0%)로 들어가고 미체결분은 종가에 담는다(578일 검정). 그 집행은 시가 이후에
일어난다. A 로 잰 성과가 G 에 몰려 있다면 **측정값과 체감 손익이 구조적으로 벌어진다.**
"""
import csv, os, statistics, sys
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE),'references','scripts'))
from universe_filters import eligible

LONG=os.path.join(HERE,'panel_ohlc_long.csv')
BENCH,NPICK,MOM='069500',5,20

def load():
    px,names=defaultdict(dict),{}
    r=csv.reader(open(LONG,encoding='utf-8')); h=next(r)
    ic,inm,idt=h.index('code'),h.index('name'),h.index('date')
    io,icl=h.index('open'),h.index('close')
    for row in r:
        try: px[row[ic]][row[idt]]=(float(row[io]),float(row[icl]))
        except ValueError: continue
        names[row[ic]]=row[inm]
    return px,names

px,names=load()
dates=sorted({d for c in px for d in px[c]})
print(f'패널 {dates[0]}~{dates[-1]} · {len(dates)}일 · 코드 {len(px)}')

# 후보 (bt_base_long 과 동일: mom20 + Rule H, 종가 기준)
cands={}
for i,d in enumerate(dates):
    if i<MOM: continue
    lst=[]
    for c in px:
        if not eligible(names.get(c,'')): continue
        a=px[c].get(dates[i-MOM]); b=px[c].get(d)
        if not(a and b): continue
        c1=px[c].get(dates[i-1]); c3=px[c].get(dates[i-3])
        if c1 and c3 and ((b[1]/c1[1]-1)*100>10 or (b[1]/c3[1]-1)*100>20): continue
        lst.append(((b[1]/a[1]-1)*100,c))
    lst.sort(reverse=True); cands[d]=lst

rets=defaultdict(dict)
for c in px:
    ds=sorted(px[c])
    for a,b in zip(ds,ds[1:]):
        if px[c][a][1]: rets[c][b]=(px[c][b][1]/px[c][a][1]-1)*100

def sigma(c,i,k=20):
    v=[rets[c].get(dates[j]) for j in range(max(1,i-k+1),i+1)]
    v=[x for x in v if x is not None]
    return statistics.stdev(v) if len(v)>=max(5,k//3) else None

def legs(c,d,n):
    a=px[c].get(d); b=px[c].get(n)
    if not a or not b or not a[1] or not b[0]: return None
    c0,o1,c1=a[1],b[0],b[1]
    return ((c1/c0-1)*100,(o1/c0-1)*100,(c1/o1-1)*100)

def run(mode,pool=30,k=20):
    out=[]
    for i,d in enumerate(dates[:-1]):
        n=dates[i+1]; cd=cands.get(d)
        if not cd or len(cd)<NPICK: continue
        if mode=='mom': picks=[c for _,c in cd[:NPICK]]
        else:
            sc=[(sigma(c,i,k),c) for _,c in cd[:pool]]
            sc=[(v,c) for v,c in sc if v is not None]
            picks=[c for _,c in sorted(sc)[:NPICK]] if len(sc)>=NPICK else [c for _,c in cd[:NPICK]]
        L=[legs(c,d,n) for c in picks]
        if any(x is None for x in L): continue
        bm=legs(BENCH,d,n)
        if bm is None: continue
        p=tuple(sum(x[j] for x in L)/len(L) for j in range(3))
        out.append((d,p,bm))
    return out

def rep(rows,lab):
    n=len(rows)
    ex=[tuple(p[j]-b[j] for j in range(3)) for _,p,b in rows]
    print(f'\n=== {lab} — 채점 {n}일 ===')
    print(f'  {"":10s}{"평균 초과":>11s}{"t":>8s}{"승률":>8s}{"누적(복리)":>12s}')
    for j,nm in ((0,'A 종가→종가'),(1,'G 갭'),(2,'B 시가→종가')):
        v=[x[j] for x in ex]
        m=statistics.mean(v); sd=statistics.stdev(v); t=m/(sd/n**0.5)
        cp=1.0; cb=1.0
        for (_,p,b) in rows:
            cp*=(1+p[j]/100); cb*=(1+b[j]/100)
        print(f'  {nm:10s}{m:+11.4f}{t:+8.2f}{sum(1 for x in v if x>0)/n*100:7.1f}%'
              f'{(cp/cb-1)*100:+11.1f}%p')
    a=statistics.mean([x[0] for x in ex]); g=statistics.mean([x[1] for x in ex])
    print(f'  → A 초과 중 갭 비중 {g/a*100:.1f}%' if abs(a)>1e-9 else '')
    return ex

M=run('mom'); V=run('lv')
exM=rep(M,'baseline (mom20+RuleH)')
exV=rep(V,'Rule LV (pool30 k20)')

print('\n=== LV − MOM (같은 날 페어) ===')
d1={d:p for d,p,_ in M}; d2={d:p for d,p,_ in V}
com=sorted(set(d1)&set(d2))
print(f'  공통 {len(com)}일')
for j,nm in ((0,'A'),(1,'G'),(2,'B')):
    v=[d2[d][j]-d1[d][j] for d in com]
    m=statistics.mean(v); sd=statistics.stdev(v)
    print(f'  {nm} {m:+.4f}%p/일 (t={m/(sd/len(v)**0.5):+.2f}) · 승 {sum(1 for x in v if x>0)}/{len(v)}')

def mdd(seq):
    x,pk,w=1.0,1.0,0.0
    for r in seq:
        x*=(1+r/100); pk=max(pk,x); w=min(w,x/pk-1)
    return w*100,(x-1)*100
print('\n=== 절대 성과를 구간별로 (MDD·누적) ===')
print(f'  {"":22s}{"A MDD":>9s}{"A 누적":>11s}{"B MDD":>9s}{"B 누적":>11s}')
for lab,rows in (('MOM',M),('LV',V),('KODEX200',None)):
    if rows is None:
        a=[b[0] for _,_,b in M]; b_=[b[2] for _,_,b in M]
    else:
        a=[p[0] for _,p,_ in rows]; b_=[p[2] for _,p,_ in rows]
    ma,ca=mdd(a); mb,cb=mdd(b_)
    print(f'  {lab:22s}{ma:>9.1f}{ca:>+10.1f}%{mb:>9.1f}{cb:>+10.1f}%')
