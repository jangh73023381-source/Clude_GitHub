# -*- coding: utf-8 -*-
"""iteration 4 — Rule ST(선정 고착 신선도): 집합 기준 재구현(순서 무관)"""
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'bt_pnl_v24.py')).read().split('def main()')[0])
def top(px,name,d,dates,k): return [c for c,_ in rank_candidates(px,name,d,dates,20)[:k]]
def sel_ST(px,name,d,dates,K=3,S=2,n=5):
    i=dates.index(d); base=top(px,name,d,dates,n+S); cur=set(base[:n])
    for j in range(1,K+1):
        if i-j<20: return base[:n]
        if set(top(px,name,dates[i-j],dates,n))!=cur: return base[:n]
    return base[:n-S]+base[n:n+S]
def stats(v):
    n=len(v);h=n//2; return sum(v)/n,sum(v[:h])/h,sum(v[h:])/(n-h),n
px,name,dates=load()
res={}
for lbl,K,S in [("baseline",0,0),("ST K2 S2",2,2),("ST K3 S2",3,2),("ST K3 S1",3,1),("ST K4 S2",4,2)]:
    xs=[];hs=[];trig=0
    for i in range(20,len(dates)-1):
        d=dates[i];dn=dates[i+1]
        pb=top(px,name,d,dates,5)
        p=pb if K==0 else sel_ST(px,name,d,dates,K,S)
        if set(p)!=set(pb): trig+=1
        xs.append(day_excess(px,p,d,dn)); hs.append(day_hits(px,name,p,d,dn))
    m,tr,te,n=stats(xs); hm,_,_,_=stats(hs); res[lbl]=(m,tr,te,hm)
    print("%-10s 발동 %2d일 | [P&L] %+.3f%%p tr %+.3f te %+.3f | [이진] %.3f종"%(lbl,trig,m*100,tr*100,te*100,hm))
b=res["baseline"]
print("\n=== 가드 ===")
for lbl in list(res)[1:]:
    r=res[lbl]; print("%-10s full %s train %s test %s -> %s"%(lbl,"▲" if r[0]>b[0] else "▼","▲" if r[1]>b[1] else "▼","▲" if r[2]>b[2] else "▼","채택후보" if (r[0]>b[0] and r[1]>b[1] and r[2]>b[2]) else "기각"))
