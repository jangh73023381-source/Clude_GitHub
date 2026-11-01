# -*- coding: utf-8 -*-
import csv, math
from collections import defaultdict
BASE='/sessions/elegant-hopeful-tesla/mnt/loop'
def excl(nm):
    n=nm.replace(' ','')
    return ('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n or '숏' in n)
px=defaultdict(dict); name={}
for src in [BASE+'/backtest/prices_long.csv',BASE+'/backtest/prices_july.csv']:
    for r in csv.DictReader(open(src,encoding='utf-8')):
        try: px[r['code']][r['date']]=float(r['close'])
        except: pass
        name.setdefault(r['code'],r['name'])
for r in csv.DictReader(open(BASE+'/prices_2026-07-03_to_2026-07-06.csv',encoding='utf-8')):
    try: px[r['code']]['20260703']=float(r['prev_close']); px[r['code']]['20260706']=float(r['next_close'])
    except: pass
    name.setdefault(r['code'],r.get('name',''))
dates=sorted({d for c in px for d in px[c]})
# theme baskets
theme=defaultdict(str)
for r in csv.DictReader(open(BASE+'/backtest/theme_map.csv',encoding='utf-8')):
    theme[r['code']]=r['theme'].strip()
SEMI={c for c,t in theme.items() if t=='반도체'}
VALCYC={c for c,t in theme.items() if t in ('자동차','증권','은행금융','조선','방산')}
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
def basket_mean(codes,d):
    vs=[mom1(c,d) for c in codes if mom1(c,d) is not None and px[c].get(d,0)>=10000]
    return sum(vs)/len(vs) if vs else None
def regime(d):  # 가치/경기민감 - 반도체 당일 상대강도 (D 종가 정보만)
    a=basket_mean(VALCYC,d); b=basket_mean(SEMI,d)
    return (a-b) if (a is not None and b is not None) else None
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
    return [c for c in px if px[c].get(d) and px[c][d]>=minp and not excl(name.get(c,''))]
def top_by(d,key,n,ruleh=True):
    cs=[]
    for c in base_cands(d):
        v=key(c,d)
        if v is None: continue
        if ruleh and ruleH(c,d): continue
        cs.append((c,v))
    cs.sort(key=lambda x:x[1],reverse=True); return [c for c,_ in cs[:n]]
def sel_base(d): return top_by(d,lambda c,d:momk(c,d,20),5)
def persist2(d,mode):
    if mode=='mom1': pool=top_by(d,mom1,10)
    else:  # sustained: mom1>0 & mom5>0, rank mom5
        cs=[(c,momk(c,d,5)) for c in base_cands(d) if mom1(c,d) is not None and momk(c,d,5) is not None and mom1(c,d)>0 and momk(c,d,5)>0 and not ruleH(c,d)]
        cs.sort(key=lambda x:x[1],reverse=True); pool=[c for c,_ in cs]
    return pool
def sel_gated(d,thr,mode):
    reg=regime(d)
    if reg is not None and reg>=thr:
        a=top_by(d,lambda c,d:momk(c,d,20),3)
        b=[c for c in persist2(d,mode) if c not in a][:2]
        p=a+b
        return (p, True) if len(p)>=5 else (sel_base(d), False)
    return (sel_base(d), False)

print("SEMI basket:",len(SEMI)," VALCYC basket:",len(VALCYC))
for thr in (0.005,0.010,0.015,0.020):
    for mode in ('mom1','sustained'):
        B=[];G=[];fb=[];fg=[];fire=0
        for i in range(20,len(dates)-1):
            d=dates[i]; dn=dates[i+1]
            b=sel_base(d)
            if len(b)<5: continue
            sb=uni_score(d,dn,b)
            g,fired=sel_gated(d,thr,mode); sg=uni_score(d,dn,g)
            if sb is None or sg is None: continue
            B.append(sb); G.append(sg)
            if fired: fire+=1; fb.append(sb); fg.append(sg)
        n=len(B); h=n//2
        base_avg=sum(B)/n; g_avg=sum(G)/n
        tag=f"thr={thr*100:.1f}% {mode:9}"
        line=f"{tag} | base={base_avg:.3f} gated={g_avg:.3f} | firing={fire}"
        if fb: line+=f" | 발동일: base={sum(fb)/len(fb):.3f} gated={sum(fg)/len(fg):.3f}"
        print(line)

print("\n=== 07-06 진단 (게이트 D=7/3) ===")
print("regime(7/3) = valcyc-semi 당일 상대강도 =", None if regime('20260703') is None else f"{regime('20260703')*100:+.2f}%p")
for thr in (0.005,0.010,0.015):
    for mode in ('mom1','sustained'):
        g,fired=sel_gated('20260703',thr,mode); s=uni_score('20260703','20260706',g)
        print(f"thr={thr*100:.1f}% {mode:9} 발동={fired} 적중 {s}/5 | "+", ".join(name.get(c,c)[:12] for c in g))
b=sel_base('20260703'); print("baseline 07-06 적중", uni_score('20260703','20260706',b),"/5")
