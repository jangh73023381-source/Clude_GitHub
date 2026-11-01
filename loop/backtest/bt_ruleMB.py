# -*- coding: utf-8 -*-
"""iteration 5 — Rule MB(모멘텀 측정 기준가 변경: 종가/종가[-20] → 종가/MA(20) 및 MA크로스 스코어)
신호 '구성' 축 — 기존 시도(윈도 길이·블렌드·필터·가중)와 구별됨."""
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'bt_pnl_v24.py')).read().split('def main()')[0])
def ma(px,c,d,dates,k):
    i=dates.index(d); vs=[px[c].get(dates[j]) for j in range(max(0,i-k+1),i+1)]
    vs=[v for v in vs if v]
    return sum(vs)/len(vs) if len(vs)>=k*0.8 else None
def rank_mb(px,name,d,dates,mode,minp=10000):
    out=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or not is_spot(name.get(c,'')): continue
        if not rule_h_ok(px,c,d,dates): continue
        if mode=='ma20':
            m20=ma(px,c,d,dates,20)
            s=(pc/m20-1.0) if m20 else None
        elif mode=='ma10_40':
            a=ma(px,c,d,dates,10); b=ma(px,c,d,dates,40)
            s=(a/b-1.0) if (a and b) else None
        else:
            m20=ma(px,c,d,dates,20); raw=mom(px,c,d,dates,20)
            s=((pc/m20-1.0)+raw)/2 if (m20 and raw is not None) else None
        if s is None: continue
        out.append((c,s))
    out.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in out[:5]]
def stats(v):
    n=len(v);h=n//2; return sum(v)/n,sum(v[:h])/h,sum(v[h:])/(n-h),n
px,name,dates=load()
res={}
sels=[("baseline mom20",lambda d: sel_baseline(px,name,d,dates)),
      ("MB1 close/MA20",lambda d: rank_mb(px,name,d,dates,'ma20')),
      ("MB2 MA10/MA40",lambda d: rank_mb(px,name,d,dates,'ma10_40')),
      ("MB3 혼합(mom20+MA20)",lambda d: rank_mb(px,name,d,dates,'mix'))]
for lbl,fn in sels:
    xs=[];hs=[]
    for i in range(40,len(dates)-1):
        d=dates[i];dn=dates[i+1];p=fn(d)
        xs.append(day_excess(px,p,d,dn)); hs.append(day_hits(px,name,p,d,dn))
    m,tr,te,n=stats(xs); hm,_,_,_=stats(hs); wi=sum(1 for x in xs if x>=0)
    res[lbl]=(m,tr,te,hm)
    print("%-20s [P&L] %+.3f%%p | tr %+.3f te %+.3f | 이김 %d/%d | [이진] %.3f종"%(lbl,m*100,tr*100,te*100,wi,n,hm))
b=res["baseline mom20"]
print("\n=== 가드 ===")
for lbl,_ in sels[1:]:
    r=res[lbl]; print("%-20s full %s train %s test %s | 이진 %s -> %s"%(lbl,"▲" if r[0]>b[0] else "▼","▲" if r[1]>b[1] else "▼","▲" if r[2]>b[2] else "▼","▲" if r[3]>b[3] else "▼","채택후보" if (r[0]>b[0] and r[1]>b[1] and r[2]>b[2]) else "기각"))
print("\n=== 오늘(D=20260723→20260724) ===")
for lbl,fn in sels:
    p=fn('20260723')
    print("%-20s 초과 %+.3f%%p 적중 %d/5 %s"%(lbl,day_excess(px,p,'20260723','20260724')*100,day_hits(px,name,p,'20260723','20260724'),[name[c][:14] for c in p]))
