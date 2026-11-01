# -*- coding: utf-8 -*-
"""In-sample screen: mom20 baseline vs mom20 + fresh-breakdown exclusion (sel-day session < thr)."""
import csv, math
from collections import defaultdict
BASE='/sessions/compassionate-happy-knuth/mnt/loop'
def load():
    px=defaultdict(dict); name={}
    for r in csv.DictReader(open(BASE+'/backtest/prices_long.csv',encoding='utf-8')):
        try: px[r['code']][r['date']]=float(r['close'])
        except: pass
        name[r['code']]=r['name']
    dates=sorted({d for c in px for d in px[c]})
    return px,name,dates
def is_spot(nm):
    n=nm.replace(' ','')
    return not('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n or '숏' in n)
def univ(px,name,d,dn,minp=10000):
    u=[]
    for c in px:
        if '숏' in name.get(c,'').replace(' ',''): continue
        pc=px[c].get(d); nc=px[c].get(dn)
        if pc and nc and pc>=minp: u.append((c,nc/pc-1))
    return u
def score(px,name,d,dn,picks):
    u=univ(px,name,d,dn)
    if not u: return None
    u.sort(key=lambda x:x[1],reverse=True); N=len(u); cut=max(1,math.ceil(N*0.1))
    rk={c:i+1 for i,(c,_) in enumerate(u)}
    return sum(1 for c in picks if c in rk and rk[c]<=cut)
def mom(px,c,d,dates,k):
    i=dates.index(d)
    if i<k: return None
    a=px[c].get(dates[i-k]); b=px[c].get(d)
    return (b/a-1) if a and b else None
def sess(px,c,d,dates):
    i=dates.index(d)
    if i<1: return None
    a=px[c].get(dates[i-1]); b=px[c].get(d)
    return (b/a-1) if a and b else None
def cum3(px,c,d,dates):
    i=dates.index(d)
    if i<3: return None
    a=px[c].get(dates[i-3]); b=px[c].get(d)
    return (b/a-1) if a and b else None
def ruleH(px,c,d,dates):
    s=sess(px,c,d,dates); c3=cum3(px,c,d,dates)
    return (s and s>0.10) or (c3 and c3>0.20)
def sel(px,name,d,dates,fresh_thr=None,n=5):
    cand=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<10000 or not is_spot(name[c]): continue
        m=mom(px,c,d,dates,20)
        if m is None: continue
        if ruleH(px,c,d,dates): continue
        if fresh_thr is not None:
            s=sess(px,c,d,dates)
            if s is not None and s<fresh_thr: continue
        cand.append((c,m))
    cand.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in cand[:n]]
px,name,dates=load()
# selection dates: need >=20 prior days and a next day for scoring
idx=range(20,len(dates)-1)
print(f"history {dates[0]}~{dates[-1]}, {len(dates)}d")
for thr in [None,-0.03,-0.02,-0.05]:
    tot=0; days=0; act=0; actwins=0; base_on_act=0
    detail=[]
    for i in idx:
        d=dates[i]; dn=dates[i+1]
        base=sel(px,name,d,dates,None)
        p=sel(px,name,d,dates,thr)
        sb=score(px,name,d,dn,base); sp=score(px,name,d,dn,p)
        if sb is None or sp is None: continue
        days+=1; tot+=sp
        if set(p)!=set(base):
            act+=1
            if sp>sb: actwins+=1
        detail.append((d,sb,sp))
    label='baseline' if thr is None else f'fresh<{thr:.0%}'
    avg=tot/days if days else 0
    print(f"{label:14} avg_hit {avg:.3f}/5  days {days}  activated {act}  act_improve {actwins}")
