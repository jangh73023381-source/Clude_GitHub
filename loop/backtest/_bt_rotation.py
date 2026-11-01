# -*- coding: utf-8 -*-
import csv, math
from collections import defaultdict
BASE='/sessions/elegant-hopeful-tesla/mnt/loop'
def excl(nm):
    n=nm.replace(' ','')
    return ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n or '숏' in n)
px=defaultdict(dict); name={}
for r in csv.DictReader(open(BASE+'/backtest/prices_long.csv',encoding='utf-8')):
    try: px[r['code']][r['date']]=float(r['close'])
    except: pass
    name[r['code']]=r['name']
for r in csv.DictReader(open(BASE+'/backtest/prices_july.csv',encoding='utf-8')):
    try: px[r['code']][r['date']]=float(r['close'])
    except: pass
    name.setdefault(r['code'],r['name'])
for r in csv.DictReader(open(BASE+'/prices_2026-07-03_to_2026-07-06.csv',encoding='utf-8')):
    try: px[r['code']]['20260703']=float(r['prev_close']); px[r['code']]['20260706']=float(r['next_close'])
    except: pass
    name.setdefault(r['code'],r.get('name',''))
dates=sorted({d for c in px for d in px[c]})
def momk(c,d,k):
    i=dates.index(d)
    if i<k: return None
    a=px[c].get(dates[i-k]); b=px[c].get(d)
    return (b/a-1) if(a and b and a>0) else None
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
def cands(d,minp=10000):
    out=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or excl(name.get(c,'')): continue
        m20=momk(c,d,20); m5=momk(c,d,5)
        if m20 is None or m5 is None: continue
        out.append((c,m20,m5))
    return out
def sel_mom20(d): 
    return [c for c,m20,m5 in sorted(cands(d),key=lambda x:x[1],reverse=True)[:5]]
def sel_mom5(d):
    return [c for c,m20,m5 in sorted(cands(d),key=lambda x:x[2],reverse=True)[:5]]
def sel_rot(d): # 20일 약세(<0) 후보 중 5일 강세 top5 = 낙폭과대 반등/로테이션
    c2=[x for x in cands(d) if x[1]<0]
    return [c for c,m20,m5 in sorted(c2,key=lambda x:x[2],reverse=True)[:5]]
res={'mom20':[],'mom5':[],'rot':[]}
for i in range(20,len(dates)-1):
    d=dates[i]; dn=dates[i+1]
    for key,fn in (('mom20',sel_mom20),('mom5',sel_mom5),('rot',sel_rot)):
        p=fn(d)
        if len(p)>=5:
            s=uni_score(d,dn,p)
            if s is not None: res[key].append(s)
for key in res:
    xs=res[key]; print(f"{key:7} 65일 평균적중/5 = {sum(xs)/len(xs):.3f}  (n={len(xs)})")
print()
print("=== 07-06 각 전략의 선정 top5 (7/3 정보) ===")
for key,fn in (('mom20',sel_mom20),('mom5',sel_mom5),('rot',sel_rot)):
    p=fn('20260703'); s=uni_score('20260703','20260706',p)
    print(f"{key}: 적중 {s}/5 | " + ", ".join(f"{name.get(c,c)[:14]}" for c in p))
