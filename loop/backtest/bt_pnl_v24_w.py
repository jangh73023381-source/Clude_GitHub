# -*- coding: utf-8 -*-
"""iteration 2 — Rule VW(비중 배분 축): 동일가중 대신 위험기반 가중.
※ 이 축은 v2.3 P&L 1차지표 도입 전에는 평가 자체가 불가능했던 신규 축(이진 채점은 비중 무관).
W1 역변동성 가중 / W2 역베타 가중 / W3 목표변동성 스케일(부분 현금)"""
import csv,os,math,statistics
from collections import defaultdict
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'bt_pnl_v24.py')).read().split('def main()')[0])

def rets(px,c,dates,i,k=20):
    out=[]
    for j in range(max(1,i-k+1),i+1):
        a=px[c].get(dates[j-1]); b=px[c].get(dates[j])
        if a and b: out.append(b/a-1.0)
    return out

def vol(px,c,dates,i,k=20):
    r=rets(px,c,dates,i,k)
    return statistics.pstdev(r) if len(r)>=5 else None

def beta(px,c,dates,i,k=20):
    rc=rets(px,c,dates,i,k); rb=rets(px,BENCH,dates,i,k)
    n=min(len(rc),len(rb))
    if n<5: return None
    rc,rb=rc[-n:],rb[-n:]
    vb=statistics.pvariance(rb)
    if vb<=0: return None
    mc=sum(rc)/n; mb=sum(rb)/n
    cov=sum((rc[t]-mc)*(rb[t]-mb) for t in range(n))/n
    return cov/vb

def day_excess_w(px,picks,w,d,dn):
    tot=sum(w); port=0.0
    for c,wi in zip(picks,w):
        a=px[c].get(d); b=px[c].get(dn)
        if a and b: port+=(wi/tot)*(b/a-1.0)
    a=px[BENCH].get(d); b=px[BENCH].get(dn); kr=(b/a-1.0) if (a and b) else 0.0
    return port-COST-kr

def wt_equal(px,picks,dates,i): return [1.0]*len(picks)
def wt_invvol(px,picks,dates,i):
    w=[]
    for c in picks:
        v=vol(px,c,dates,i); w.append(1.0/max(v,1e-4) if v else 1.0)
    return w
def wt_invbeta(px,picks,dates,i):
    w=[]
    for c in picks:
        b=beta(px,c,dates,i)
        w.append(1.0/max(abs(b),0.15) if b is not None else 1.0)
    return w
def wt_targetvol(px,picks,dates,i,target=0.010):
    """W3: 동일가중 포트 변동성이 목표(1.0%/일) 초과하면 그만큼 현금(수익 0)으로 축소"""
    vs=[vol(px,c,dates,i) for c in picks]
    vs=[v for v in vs if v]
    pv=(sum(vs)/len(vs)) if vs else None
    if not pv: return [1.0]*len(picks)
    k=min(1.0,target/pv)
    return [k]*len(picks)+[max(0.0,1.0-k)*len(picks)]  # 마지막=현금 슬롯

def track_w(px,name,dates,selfn,wtfn,start=20):
    xs=[];dd=[]
    for i in range(start,len(dates)-1):
        d=dates[i];dn=dates[i+1]
        picks=selfn(px,name,d,dates)
        w=wtfn(px,picks,dates,i)
        if len(w)==len(picks)+1:   # 현금 슬롯 포함
            tot=sum(w); port=0.0
            for c,wi in zip(picks,w[:-1]):
                a=px[c].get(d);b=px[c].get(dn)
                if a and b: port+=(wi/tot)*(b/a-1.0)
            a=px[BENCH].get(d);b=px[BENCH].get(dn);kr=(b/a-1.0) if (a and b) else 0.0
            xs.append(port-COST-kr)
        else:
            xs.append(day_excess_w(px,picks,w,d,dn))
        dd.append(d)
    return xs,dd

def stats(v):
    n=len(v); h=n//2
    return sum(v)/n, sum(v[:h])/h, sum(v[h:])/(n-h), n

px,name,dates=load()
print("패널:%d종×%d일 %s~%s"%(len(px),len(dates),dates[0],dates[-1]))
a=px[BENCH][dates[20]]; b=px[BENCH][dates[-1]]
print("벤치(KODEX200) 표본구간 수익 %+.1f%% (%s~%s)\n"%((b/a-1)*100,dates[20],dates[-1]))
variants=[("baseline 동일가중",wt_equal),("W1 역변동성 가중",wt_invvol),
          ("W2 역베타 가중",wt_invbeta),("W3 목표변동성 1.0%/일",wt_targetvol)]
res={}
for lbl,wf in variants:
    xs,dd=track_w(px,name,dates,sel_baseline,wf)
    m,tr,te,n=stats(xs); wi=sum(1 for x in xs if x>=0)
    sd=statistics.pstdev(xs)
    res[lbl]=(m,tr,te)
    print("%-20s 평균초과 %+.3f%%p | train %+.3f%%p test %+.3f%%p | 지수이김 %d/%d | IR %.3f"%(
        lbl,m*100,tr*100,te*100,wi,n,(m/sd if sd else 0)))
bm,btr,bte=res["baseline 동일가중"]
print("\n=== 과최적화 가드 ===")
for lbl,_ in variants[1:]:
    m,tr,te=res[lbl]
    ok=(m>bm and tr>btr and te>bte)
    print("%-20s full %s train %s test %s -> %s"%(lbl,"▲" if m>bm else "▼","▲" if tr>btr else "▼","▲" if te>bte else "▼","**채택후보**" if ok else "기각"))
print("\n=== 오늘(D=20260723→20260724) in-sample ===")
i=dates.index('20260723')
picks=sel_baseline(px,name,'20260723',dates)
for lbl,wf in variants:
    w=wf(px,picks,dates,i)
    if len(w)==len(picks)+1:
        tot=sum(w);port=0.0
        for c,wi_ in zip(picks,w[:-1]):
            port+=(wi_/tot)*(px[c]['20260724']/px[c]['20260723']-1)
        kr=px[BENCH]['20260724']/px[BENCH]['20260723']-1
        ex=port-COST-kr
    else:
        ex=day_excess_w(px,picks,w,'20260723','20260724')
    print("%-20s 초과 %+.3f%%p"%(lbl,ex*100))
