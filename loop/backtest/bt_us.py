# -*- coding: utf-8 -*-
import sys; sys.path.insert(0,'/sessions/exciting-sharp-albattani/mnt/loop/backtest')
from bt_engine import load, score, is_spot
import csv, statistics as st
px,name,dates=load()
# US returns by US date
us={}
rows=list(csv.DictReader(open('us_sox.csv')))
for i in range(1,len(rows)):
    d=rows[i]['date']; p=rows[i-1]
    us[d]={'sox':float(rows[i]['sox'])/float(p['sox'])-1, 'ixic':float(rows[i]['ixic'])/float(p['ixic'])-1}
usdates=sorted(us)
def us_signal(selday):  # 룩어헤드 금지: 한국 선정일 selday 시점에 공개된 최신 미국일(<selday)
    cand=[d for d in usdates if d<selday]
    return us[cand[-1]] if cand else None

def ret(c,d,k):
    i=dates.index(d)
    if i<k: return None
    a=px[c].get(dates[i-k]); b=px[c].get(d)
    return (b/a-1.0) if (a and b) else None
SEMI=('반도체','AI','HBM','반도','테크','전공정','소부장','메모리')
def is_semi(nm): return any(k in nm for k in SEMI)

def sel(d,strat,n=5):
    sg=us_signal(d); sox=sg['sox'] if sg else 0.0
    s=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<10000 or not is_spot(name[c]): continue
        m=ret(c,d,20)
        if m is None: continue
        key=m
        if strat=='us_semitilt' and sox>0.015 and is_semi(name[c]): key=m+1.0   # 미국 반도체 강세시 반도체 우선
        if strat=='us_semitilt_neg' and sox<-0.02 and is_semi(name[c]): key=m-1.0 # 미국 약세시 반도체 후순위
        s.append((c,key))
    s.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in s[:n]]

def run(strat,lo,hi):
    H=[];E=[]
    for i in range(20,len(dates)-1):
        if i<lo or i>=hi: continue
        d,dn=dates[i],dates[i+1]
        p=sel(d,strat)
        if len(p)<5: continue
        sc=score(px,name,d,dn,p)
        if not sc or sc['avg_excess'] is None: continue
        H.append(sc['hit']); E.append(sc['avg_excess']*100)
    return (len(H), st.mean(H) if H else 0, st.mean(E) if E else 0)

# 진단: 한국 ETF 익일 평균수익률 vs 선정일 직전 미국 SOX (상관)
xs=[];ys=[]
for i in range(20,len(dates)-1):
    d,dn=dates[i],dates[i+1]
    sg=us_signal(d)
    if not sg: continue
    rr=[px[c][dn]/px[c][d]-1 for c in px if px[c].get(d) and px[c].get(dn) and px[c][d]>=10000]
    if rr: xs.append(sg['sox']); ys.append(st.mean(rr))
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    cov=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    va=sum((x-ma)**2 for x in a)**0.5; vb=sum((y-mb)**2 for y in b)**0.5
    return cov/(va*vb) if va and vb else 0
print(f"진단: 한국ETF 익일평균수익 vs 직전 美SOX(룩어헤드 없는 lag) 상관 = {corr(xs,ys):+.2f} (n={len(xs)})")
n=len(dates); mid=20+(n-1-20)//2
print(f"\n{'전략':<16}{'전체적중':>8}{'전체초과%':>9}{'train적중':>9}{'test적중':>9}")
for s in ['mom20','us_semitilt','us_semitilt_neg']:
    da,ha,ea=run(s,20,n-1); _,h1,_=run(s,20,mid); _,h2,_=run(s,mid,n-1)
    print(f"{s:<16}{ha:>8.2f}{ea:>9.2f}{h1:>9.2f}{h2:>9.2f}")
