# -*- coding: utf-8 -*-
import csv, math
from collections import defaultdict
BASE='/sessions/elegant-hopeful-tesla/mnt/loop'
BENCH='069500'
def is_spot(nm):
    n=nm.replace(' ','')
    return not('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n)
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
# theme map: semiconductor set
semi=set()
for r in csv.DictReader(open(BASE+'/backtest/theme_map.csv',encoding='utf-8')):
    if r['theme'].strip()=='반도체': semi.add(r['code'])
# sox returns by date
sox={}
rows=[r for r in csv.DictReader(open(BASE+'/backtest/us_sox.csv',encoding='utf-8'))]
sd=[r['date'] for r in rows]; sv=[float(r['sox']) for r in rows]
soxret={sd[i]: (sv[i]/sv[i-1]-1.0) for i in range(1,len(sd))}
def latest_sox_ret(d):
    # latest US sox date <= d
    cand=[x for x in soxret if x<=d]
    if not cand: return None
    return soxret[max(cand)]
def momk(c,d,k):
    i=dates.index(d)
    if i<k: return None
    a=px[c].get(dates[i-k]); b=px[c].get(d)
    return (b/a-1.0) if (a and b and a>0) else None
def sess(c,d):
    i=dates.index(d)
    if i<1: return None
    a=px[c].get(dates[i-1]); b=px[c].get(d)
    return (b/a-1.0) if (a and b and a>0) else None
def cum3(c,d):
    i=dates.index(d)
    if i<3: return None
    a=px[c].get(dates[i-3]); b=px[c].get(d)
    return (b/a-1.0) if (a and b and a>0) else None
def ruleH(c,d):
    s=sess(c,d); c3=cum3(c,d)
    return (s is not None and s>0.10) or (c3 is not None and c3>0.20)
def cand20(d,minp=10000):
    cc=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or not is_spot(name.get(c,'')): continue
        m=momk(c,d,20)
        if m is not None: cc.append((c,m))
    cc.sort(key=lambda x:x[1],reverse=True); return cc
def usc_score(d,dn,picks,minp=10000):
    u=[]
    for c in px:
        pc=px[c].get(d); nc=px[c].get(dn)
        if pc and nc and pc>=minp: u.append((c,nc/pc-1.0))
    if not u: return None
    u.sort(key=lambda x:x[1],reverse=True); N=len(u); cut=max(1,math.ceil(N*0.10))
    rank={c:i+1 for i,(c,_) in enumerate(u)}
    hit=sum(1 for c in picks if c in rank and rank[c]<=cut)
    pcts=[(rank[c]-1)/N*100 for c in picks if c in rank]
    return {'hit':hit,'avg_pct':(sum(pcts)/len(pcts) if pcts else None)}
def sel_base(d): return [c for c,_ in cand20(d) if not ruleH(c,d)][:5]
def sel_soxgate(d,thr):
    fired = (latest_sox_ret(d) is not None and latest_sox_ret(d)<=thr)
    out=[]
    for c,_ in cand20(d):
        if ruleH(c,d): continue
        if fired and c in semi: continue
        out.append(c)
        if len(out)==5: break
    return out, fired
for thr in (-0.03,-0.04,-0.05):
    B=[];G=[];fire=0;fb=[];fg=[];frows=[]
    for i in range(20,len(dates)-1):
        d=dates[i]; dn=dates[i+1]
        b=sel_base(d)
        if len(b)<5: continue
        sb=usc_score(d,dn,b)
        g,fired=sel_soxgate(d,thr); sg=usc_score(d,dn,g)
        if not sb or not sg: continue
        B.append(sb); G.append(sg)
        if set(g)!=set(b):
            fire+=1; fb.append(sb['hit']); fg.append(sg['hit']); frows.append((d,dn,sb['hit'],sg['hit']))
    ah=sum(x['hit'] for x in B)/len(B); gh=sum(x['hit'] for x in G)/len(G)
    ap=sum(x['avg_pct'] for x in B)/len(B); gp=sum(x['avg_pct'] for x in G)/len(G)
    print(f"thr={thr*100:.0f}% days={len(B)} base_hit={ah:.3f} gate_hit={gh:.3f} | base_pct={ap:.1f} gate_pct={gp:.1f} | firing={fire}")
    if fb: print(f"   firing-only: base_hit={sum(fb)/len(fb):.3f} gate_hit={sum(fg)/len(fg):.3f}  rows={frows}")
