# -*- coding: utf-8 -*-
"""iteration 3~4 — Rule R'(다일런업 소프트 디웨이팅 P&L 재평가) / Rule ST(선정 고착 신선도)"""
import csv,os,math
from collections import defaultdict
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'bt_pnl_v24.py')).read().split('def main()')[0])

def sel_R(px,name,d,dates,lam=1.0,thr=0.05,n=5):
    cand=rank_candidates(px,name,d,dates,20)
    out=[]
    for c,m in cand:
        s1=mom(px,c,d,dates,1) or 0.0
        out.append((c,m-lam*max(0.0,s1-thr)))
    out.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in out[:n]]

_hist={}
def sel_ST(px,name,d,dates,K=3,S=2,n=5):
    """선정 고착: 직전 K영업일 연속 top5 집합이 동일하면 하위 S슬롯을 차순위(6위~)로 교체"""
    i=dates.index(d)
    base=[c for c,_ in rank_candidates(px,name,d,dates,20)[:n+S]]
    cur=tuple(base[:n])
    stale=True
    for j in range(1,K+1):
        if i-j<20: stale=False; break
        prev=tuple(c for c,_ in rank_candidates(px,name,dates[i-j],dates,20)[:n])
        if prev!=cur: stale=False; break
    if not stale: return list(cur)
    return base[:n-S]+base[n:n+S]

def day_hits2(px,name,picks,d,dn): return day_hits(px,name,picks,d,dn)

def track2(px,name,dates,fn,start=20):
    xs=[];hs=[]
    for i in range(start,len(dates)-1):
        d=dates[i];dn=dates[i+1];p=fn(px,name,d,dates)
        xs.append(day_excess(px,p,d,dn)); hs.append(day_hits(px,name,p,d,dn))
    return xs,hs
def stats(v):
    n=len(v);h=n//2
    return sum(v)/n,sum(v[:h])/h,sum(v[h:])/(n-h),n

px,name,dates=load()
variants=[("baseline mom20+H",sel_baseline),
          ("R' lam1.0 thr5%",lambda p,nm,d,dt: sel_R(p,nm,d,dt,1.0,0.05)),
          ("R' lam1.0 thr3%",lambda p,nm,d,dt: sel_R(p,nm,d,dt,1.0,0.03)),
          ("R' lam2.0 thr5%",lambda p,nm,d,dt: sel_R(p,nm,d,dt,2.0,0.05)),
          ("ST K3 S2",lambda p,nm,d,dt: sel_ST(p,nm,d,dt,3,2)),
          ("ST K5 S2",lambda p,nm,d,dt: sel_ST(p,nm,d,dt,5,2)),
          ("ST K3 S1",lambda p,nm,d,dt: sel_ST(p,nm,d,dt,3,1))]
res={}
for lbl,fn in variants:
    xs,hs=track2(px,name,dates,fn)
    m,tr,te,n=stats(xs); hm,htr,hte,_=stats(hs); wi=sum(1 for x in xs if x>=0)
    res[lbl]=(m,tr,te,hm)
    print("%-18s [P&L] %+.3f%%p | tr %+.3f te %+.3f | 이김 %d/%d | [이진] %.3f종"%(lbl,m*100,tr*100,te*100,wi,n,hm))
b=res["baseline mom20+H"]
print("\n=== 과최적화 가드 ===")
for lbl,_ in variants[1:]:
    r=res[lbl]; ok=(r[0]>b[0] and r[1]>b[1] and r[2]>b[2])
    print("%-18s full %s train %s test %s | 이진 %s -> %s"%(lbl,"▲" if r[0]>b[0] else "▼","▲" if r[1]>b[1] else "▼","▲" if r[2]>b[2] else "▼","▲" if r[3]>b[3] else "▼","**채택후보**" if ok else "기각"))
print("\n=== 오늘(D=20260723→20260724) in-sample ===")
for lbl,fn in variants:
    p=fn(px,name,'20260723',dates)
    print("%-18s 초과 %+.3f%%p 적중 %d/5 %s"%(lbl,day_excess(px,p,'20260723','20260724')*100,day_hits(px,name,p,'20260723','20260724'),[name[c][:14] for c in p]))
# 고착 진단
print("\n=== 선정 고착 진단(최근 12영업일 mom20 top5 변화) ===")
prev=None
for d in dates[-12:-1]:
    cur=tuple(c for c,_ in rank_candidates(px,name,d,dates,20)[:5])
    print(d, "동일" if cur==prev else "변경", [name[c][:12] for c in cur])
    prev=cur
