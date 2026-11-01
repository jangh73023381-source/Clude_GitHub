# -*- coding: utf-8 -*-
import csv, math, statistics as st
from collections import defaultdict
BASE='/sessions/elegant-hopeful-tesla/mnt/loop'
def excl(nm):
    n=nm.replace(' ','')
    return ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n or '숏' in n)
px=defaultdict(dict); name={}
for src,mode in [(BASE+'/backtest/prices_long.csv','l'),(BASE+'/backtest/prices_july.csv','l')]:
    for r in csv.DictReader(open(src,encoding='utf-8')):
        try: px[r['code']][r['date']]=float(r['close'])
        except: pass
        name.setdefault(r['code'],r['name'])
for r in csv.DictReader(open(BASE+'/prices_2026-07-03_to_2026-07-06.csv',encoding='utf-8')):
    try: px[r['code']]['20260703']=float(r['prev_close']); px[r['code']]['20260706']=float(r['next_close'])
    except: pass
    name.setdefault(r['code'],r.get('name',''))
dates=sorted({d for c in px for d in px[c]})
def rr(c,d0,d1):
    a=px[c].get(d0); b=px[c].get(d1)
    return (b/a-1) if(a and b and a>0) else None
def momk(c,d,k):
    i=dates.index(d)
    return rr(c,dates[i-k],d) if i>=k else None
def mom1(c,d): return momk(c,d,1)
def cum3(c,d): return momk(c,d,3)
def ruleH(c,d):
    s=mom1(c,d); c3=cum3(c,d)
    return (s is not None and s>0.10) or (c3 is not None and c3>0.20)
def uni_score(d,dn,picks,minp=10000):
    u=[]
    for c in px:
        if '숏' in name.get(c,'').replace(' ',''): continue
        pc=px[c].get(d); nc=px[c].get(dn)
        if pc and nc and pc>=minp: u.append((c,nc/pc-1))
    if not u: return None
    u.sort(key=lambda x:x[1],reverse=True); N=len(u); cut=max(1,math.ceil(N*0.1))
    rank={c:i+1 for i,(c,_) in enumerate(u)}
    return sum(1 for c in picks if c in rank and rank[c]<=cut)
def base_cands(d,minp=10000):
    out=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or excl(name.get(c,'')): continue
        out.append(c)
    return out
def top_by(d,key,n,ruleh=True):
    cs=[]
    for c in base_cands(d):
        v=key(c,d)
        if v is None: continue
        if ruleh and ruleH(c,d): continue
        cs.append((c,v))
    cs.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in cs[:n]]
def sel_mom20(d): return top_by(d,lambda c,d:momk(c,d,20),5)
def sel_persist5(d): return top_by(d,mom1,5)             # N1: 전일 단일세션 상위5 (RuleH)
def sel_hybrid32(d):                                      # N2: mom20 top3 + mom1 top2
    a=top_by(d,lambda c,d:momk(c,d,20),3); 
    b=[c for c in top_by(d,mom1,8) if c not in a][:2]
    return a+b
def sel_hybrid41(d):                                      # N3: mom20 top4 + mom1 top1
    a=top_by(d,lambda c,d:momk(c,d,20),4)
    b=[c for c in top_by(d,mom1,8) if c not in a][:1]
    return a+b
strats={'mom20(base)':sel_mom20,'N1_persist5':sel_persist5,'N2_20x3+1x2':sel_hybrid32,'N3_20x4+1x1':sel_hybrid41}
res={k:[] for k in strats}
for i in range(20,len(dates)-1):
    d=dates[i]; dn=dates[i+1]
    for k,fn in strats.items():
        p=fn(d)
        if len(p)>=5:
            s=uni_score(d,dn,p)
            if s is not None: res[k].append(s)
print("=== 65일 패널 (숏 제외 유니버스) ===")
for k in strats:
    xs=res[k]; ge3=sum(1 for x in xs if x>=3)/len(xs)*100
    print(f"{k:14} 평균적중/5={sum(xs)/len(xs):.3f}  ≥1적중%={sum(1 for x in xs if x>=1)/len(xs)*100:.0f}  ≥3%={ge3:.0f}  (n={len(xs)})")
# train/test split (front 33 / back 32)
print("\n=== train(앞32)/test(뒤32) 분할 ===")
for k in strats:
    xs=res[k]; h=len(xs)//2
    print(f"{k:14} train={sum(xs[:h])/h:.3f}  test={sum(xs[h:])/(len(xs)-h):.3f}")
print("\n=== 07-06 각 전략 선정·적중 (7/3 정보) ===")
for k,fn in strats.items():
    p=fn('20260703'); s=uni_score('20260703','20260706',p)
    print(f"{k:14} 적중 {s}/5 | "+", ".join(name.get(c,c)[:13] for c in p))

print("\n\n===== 정교화 변형(지속 리더) =====")
def mom5(c,d): return momk(c,d,5)
def sustained_pool(d):  # 다일 지속: mom1>0 & mom5>0 & RuleH통과, mom5로 랭크
    cs=[]
    for c in base_cands(d):
        m1=mom1(c,d); m5=mom5(c,d)
        if m1 is None or m5 is None: continue
        if ruleH(c,d): continue
        if m1>0 and m5>0: cs.append((c,m5))
    cs.sort(key=lambda x:x[1],reverse=True); return [c for c,_ in cs]
def sel_N4(d): return sustained_pool(d)[:5]
def sel_N5(d): # mom20 top3 + 지속리더 top2
    a=top_by(d,lambda c,d:momk(c,d,20),3)
    b=[c for c in sustained_pool(d) if c not in a][:2]
    return a+b
more={'N4_지속리더5':sel_N4,'N5_20x3+지속x2':sel_N5}
r2={k:[] for k in more}
for i in range(20,len(dates)-1):
    d=dates[i]; dn=dates[i+1]
    for k,fn in more.items():
        p=fn(d)
        if len(p)>=5:
            s=uni_score(d,dn,p)
            if s is not None: r2[k].append(s)
for k in more:
    xs=r2[k]; h=len(xs)//2
    print(f"{k:16} 평균={sum(xs)/len(xs):.3f} train={sum(xs[:h])/h:.3f} test={sum(xs[h:])/(len(xs)-h):.3f} (n={len(xs)})")
for k,fn in more.items():
    p=fn('20260703'); s=uni_score('20260703','20260706',p)
    print(f"{k:16} 07-06 적중 {s}/5 | "+", ".join(name.get(c,c)[:13] for c in p))
