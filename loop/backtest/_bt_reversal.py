# -*- coding: utf-8 -*-
import csv, math
from collections import defaultdict
BASE='/sessions/elegant-hopeful-tesla/mnt/loop'
BENCH='069500'
def is_spot(nm):
    n=nm.replace(' ','')
    return not('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n)
# merge panel: prices_long (03-03~06-30) + prices_july (07-01..03) + 07-03->07-06 file
px=defaultdict(dict); name={}
def add(path, mode):
    for r in csv.DictReader(open(path,encoding='utf-8')):
        c=r['code']
        if mode=='long':
            try: px[c][r['date']]=float(r['close'])
            except: pass
            name[c]=r['name']
        elif mode=='pair':
            try:
                px[c]['20260703']=float(r['prev_close']); px[c]['20260706']=float(r['next_close'])
            except: pass
            name.setdefault(c,r.get('name',''))
add(BASE+'/backtest/prices_long.csv','long')
add(BASE+'/backtest/prices_july.csv','long')
add(BASE+'/prices_2026-07-03_to_2026-07-06.csv','pair')
dates=sorted({d for c in px for d in px[c]})
print('panel codes',len(px),'days',len(dates),dates[0],'~',dates[-1])

def ret(c,d0,d1):
    a=px[c].get(d0); b=px[c].get(d1)
    return (b/a-1.0) if (a and b and a>0) else None
def momk(c,d,k):
    i=dates.index(d)
    if i<k: return None
    return ret(c,dates[i-k],d)
def cumk(c,d,k):  # k-session cumulative through d
    i=dates.index(d)
    if i<k: return None
    return ret(c,dates[i-k],d)
def sess(c,d):
    i=dates.index(d)
    if i<1: return None
    return ret(c,dates[i-1],d)

def universe_score(d,dnext,picks,minp=10000):
    u=[]
    for c in px:
        pc=px[c].get(d); nc=px[c].get(dnext)
        if pc and nc and pc>=minp: u.append((c,nc/pc-1.0))
    if not u: return None
    u.sort(key=lambda x:x[1],reverse=True)
    N=len(u); cutoff=max(1,math.ceil(N*0.10))
    rank={c:i+1 for i,(c,_) in enumerate(u)}; rr={c:r for c,r in u}
    bench=rr.get(BENCH,0.0); hit=0; pcts=[]
    for c in picks:
        if c in rank:
            hit+= 1 if rank[c]<=cutoff else 0; pcts.append((rank[c]-1)/N*100)
    return {'N':N,'hit':hit,'avg_pct':(sum(pcts)/len(pcts) if pcts else None),'npick':len(picks)}

def cand_mom20(d,minp=10000):
    cc=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or not is_spot(name.get(c,'')): continue
        m=momk(c,d,20)
        if m is not None: cc.append((c,m))
    cc.sort(key=lambda x:x[1],reverse=True)
    return cc

def ruleH(c,d):  # exclude prev single-session >10% or 3-day cum >20%
    s=sess(c,d); c3=cumk(c,d,3)
    return (s is not None and s>0.10) or (c3 is not None and c3>0.20)

def sel_baseline(d):
    return [c for c,_ in cand_mom20(d) if not ruleH(c,d)][:5]

def sel_reversal(d,thr):  # + exclude cum3<=thr (sharp recent drawdown)
    out=[]
    for c,_ in cand_mom20(d):
        if ruleH(c,d): continue
        c3=cumk(c,d,3)
        if c3 is not None and c3<=thr: continue
        out.append(c)
        if len(out)==5: break
    return out

# scoreable days: need 20-session warmup and a dnext
si=20
res={'base':[], 'rev06':[], 'rev08':[]}
fire={'rev06':0,'rev08':0}
detail=[]
for i in range(si, len(dates)-1):
    d=dates[i]; dn=dates[i+1]
    b=sel_baseline(d)
    if len(b)<5: continue
    sb=universe_score(d,dn,b)
    if not sb: continue
    r6=sel_reversal(d,-0.06); r8=sel_reversal(d,-0.08)
    s6=universe_score(d,dn,r6); s8=universe_score(d,dn,r8)
    res['base'].append(sb); res['rev06'].append(s6); res['rev08'].append(s8)
    if set(r6)!=set(b): fire['rev06']+=1
    if set(r8)!=set(b): fire['rev08']+=1
    detail.append((d,dn,sb['hit'],s6['hit'] if s6 else None,s8['hit'] if s8 else None, set(r6)!=set(b)))

def summ(key):
    xs=[x for x in res[key] if x]
    ah=sum(x['hit'] for x in xs)/len(xs)
    ap=sum(x['avg_pct'] for x in xs if x['avg_pct'] is not None)/len(xs)
    return ah,ap,len(xs)
for key in ['base','rev06','rev08']:
    ah,ap,n=summ(key)
    extra=f" firing={fire[key]}" if key in fire else ""
    print(f"{key:8} days={n} avg_hit/5={ah:.3f} avg_pctile={ap:.1f}{extra}")

# firing-day only comparison (rev06)
print("\n=== rev06 firing-day-only (base vs rev06) ===")
fb=[]; fr=[]
for (d,dn,hb,h6,h8,fired) in detail:
    if fired:
        fb.append(hb); fr.append(h6)
print(f"firing days={len(fb)}  base avg_hit={sum(fb)/len(fb):.3f}  rev06 avg_hit={sum(fr)/len(fr):.3f}")
print("firing-day rows (date, base_hit, rev06_hit):")
for (d,dn,hb,h6,h8,fired) in detail:
    if fired: print(f"  {d}->{dn} base {hb} rev06 {h6}")
