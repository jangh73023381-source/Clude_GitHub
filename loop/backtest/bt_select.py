# -*- coding: utf-8 -*-
"""여러 선정 전략을 train/test 분할로 비교. 룩어헤드 금지. 지표=평균적중/5, 초과수익(KODEX200)."""
import sys; sys.path.insert(0,'/sessions/exciting-sharp-albattani/mnt/loop/backtest')
from bt_engine import load, score, is_spot
import statistics as st
px,name,dates=load()

BROADKEY=('200','코스닥150')
def is_broad(nm):
    n=nm.replace(' ','')
    return ('200' in n) or ('코스닥150' in n) or ('코스피' in n and '인덱스' in n)
THEME=('반도체','AI','전력','우주','로봇','HBM','반도','테크','원자력','SMR')
def is_theme(nm): return any(k in nm for k in THEME)

def ret(c,d,k):
    i=dates.index(d)
    if i<k: return None
    a=px[c].get(dates[i-k]); b=px[c].get(d)
    return (b/a-1.0) if (a and b) else None
def prevday(c,d): return ret(c,d,1)

def candidates(d,minp=10000):
    out=[]
    for c in px:
        pc=px[c].get(d)
        if pc and pc>=minp and is_spot(name[c]): out.append(c)
    return out

def sel(d,strat,n=5):
    cs=candidates(d)
    def m5(c): return ret(c,d,5)
    def m20(c): return ret(c,d,20)
    scored=[]
    for c in cs:
        a=m5(c)
        if a is None: continue
        pv=prevday(c,d)
        spike = pv is not None and pv>0.10
        if strat=='mom5': key=a
        elif strat=='mom5_nospike': 
            if spike: continue
            key=a
        elif strat=='mom20':
            b=m20(c); 
            if b is None: continue
            key=b
        elif strat=='blend':
            b=m20(c)
            if b is None: continue
            key=a+b
        elif strat=='theme_nospike':
            if spike or not is_theme(name[c]): continue
            key=a
        elif strat=='theme_nobroad_nospike':
            if spike or is_broad(name[c]) or not is_theme(name[c]): continue
            key=a
        elif strat=='nobroad_nospike':
            if spike or is_broad(name[c]): continue
            key=a
        else: key=a
        scored.append((c,key))
    scored.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in scored[:n]]

def run(strat,lo,hi):
    H=[];E=[]
    for i in range(max(20,lo),hi):
        if i>=len(dates)-1: break
        d,dn=dates[i],dates[i+1]
        p=sel(d,strat)
        if len(p)<5: continue
        s=score(px,name,d,dn,p)
        if not s or s['avg_excess'] is None: continue
        H.append(s['hit']); E.append(s['avg_excess']*100)
    return (len(H), st.mean(H) if H else 0, st.mean(E) if E else 0)

n=len(dates); mid=20+(n-1-20)//2
strats=['mom5','mom5_nospike','mom20','blend','nobroad_nospike','theme_nospike','theme_nobroad_nospike']
print(f"{'전략':<24}{'train적중':>9}{'train초과%':>10}{'test적중':>9}{'test초과%':>10}{'전체적중':>9}")
for s in strats:
    d1,h1,e1=run(s,20,mid); d2,h2,e2=run(s,mid,n-1); da,ha,ea=run(s,20,n-1)
    print(f"{s:<24}{h1:>9.2f}{e1:>10.2f}{h2:>9.2f}{e2:>10.2f}{ha:>9.2f}")
print(f"\ntrain={mid-20}일, test={n-1-mid}일")
