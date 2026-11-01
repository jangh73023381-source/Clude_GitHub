#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Iteration 2 distinct variants:
 (P) cash tilt only when gate active on BOTH D and D-1 (sustained stress).
 (H) FX-hedged foreign index tilt on gate days.
 (G) cash+gold tilt on gate days.
Same look-ahead-free framing as _bt_cashgate.py."""
import csv, math
base='/sessions/funny-stoic-heisenberg/mnt/loop'
panel={}; names={}
for r in csv.DictReader(open(base+'/panel_close.csv',encoding='utf-8')):
    c=r['code']; panel.setdefault(c,{})[r['date']]=float(r['close'])
    if r['name']: names[c]=r['name']
dates=sorted({d for dd in panel.values() for d in dd})
liq={}
for r in csv.DictReader(open(base+'/etf_universe.csv',encoding='utf-8-sig')):
    try: liq[r['티커'].strip()]=float(r['거래대금'])
    except: pass
def excl(nm):
    n=(nm or '').replace(' ','')
    return ('레버리지' in n or '2X' in n.upper() or '인버스' in n or '곱버스' in n or '숏' in n)
CASH_KW=['머니마켓','MMF','CD금리','CD1년','KOFR','초단기채','금리투자','금리플러스액티브','금리액티브']
def is_cash(nm):
    n=(nm or '').replace(' ','');return any(k in n for k in CASH_KW)
def is_gold(nm): return '골드' in (nm or '') or '금선물' in (nm or '')
def is_hedgedus(nm):
    n=(nm or '')
    return ('(H)' in n) and ('미국' in n or 'S&P' in n or '나스닥' in n)
cash_codes=sorted([c for c in panel if is_cash(names.get(c,'')) and not excl(names.get(c,''))],key=lambda c:-liq.get(c,0))
gold_codes=sorted([c for c in panel if is_gold(names.get(c,'')) and not excl(names.get(c,''))],key=lambda c:-liq.get(c,0))
hus_codes=sorted([c for c in panel if is_hedgedus(names.get(c,'')) and not excl(names.get(c,''))],key=lambda c:-liq.get(c,0))
print('cash',len(cash_codes),'gold',len(gold_codes),'hedgedUS',[names[c][:20] for c in hus_codes])
IDX='069500'
def mom20_ruleh(di):
    D=dates[di]; d20=dates[di-20]; d1=dates[di-1]; d3=dates[di-3]
    cand=[]
    for c,dd in panel.items():
        if excl(names.get(c,'')): continue
        pc=dd.get(D); p20=dd.get(d20)
        if not pc or not p20 or pc<10000: continue
        sess=(pc/dd[d1]-1) if dd.get(d1) else 0
        cum3=(pc/dd[d3]-1) if dd.get(d3) else 0
        if sess>0.10 or cum3>0.20: continue
        cand.append((c,pc/p20-1))
    cand.sort(key=lambda x:x[1],reverse=True); return cand[:5]
def hits(picks,di):
    D=dates[di]; N=dates[di+1]; uni=[]
    for c,dd in panel.items():
        if '숏' in names.get(c,''): continue
        pc=dd.get(D); nc=dd.get(N)
        if not pc or not nc or pc<10000: continue
        uni.append((c,nc/pc-1))
    uni.sort(key=lambda x:x[1],reverse=True); Nn=len(uni); cut=max(1,math.ceil(Nn*0.10))
    top=set(c for c,_ in uni[:cut]); return sum(1 for c in picks if c in top)
def gret(di):
    D=dates[di]; d1=dates[di-1]
    a=panel.get(IDX,{}).get(D); b=panel.get(IDX,{}).get(d1)
    return (a/b-1) if a and b else 0
def variant(di,mode,thr):
    D=dates[di]; g=gret(di)<=thr
    base5=[c for c,_ in mom20_ruleh(di)]
    if mode=='P':
        g=g and (gret(di-1)<=thr)  # sustained: D and D-1
        pool=cash_codes
    elif mode=='H': pool=hus_codes
    elif mode=='G': pool=(cash_codes[:1]+gold_codes[:1]) if gold_codes else cash_codes
    else: pool=cash_codes
    if not g: return base5,False
    avail=[c for c in pool if panel[c].get(D,0)>=10000]
    if len(avail)<2: return base5,False
    return base5[:3]+avail[:2],True

for thr in (-0.02,-0.025):
    days=[i for i in range(22,len(dates)-1)]
    res={}
    base_all=[]
    for di in days: base_all.append(hits([c for c,_ in mom20_ruleh(di)],di))
    print('\n===== GATE_THR %.1f%%  baseline avg %.3f (%d days) ====='%(thr*100,sum(base_all)/len(base_all),len(base_all)))
    for mode in ('P','H','G'):
        oh=[]; fire=[]; bf=[]; of=[]
        for k,di in enumerate(days):
            op,fired=variant(di,mode,thr); h=hits(op,di); oh.append(h)
            if fired: fire.append(dates[di]); bf.append(base_all[k]); of.append(h)
        print(' mode %s: overall %.3f | fire %d days base %.3f -> %.3f | %s'%(
            mode,sum(oh)/len(oh),len(fire),(sum(bf)/len(bf) if fire else 0),(sum(of)/len(of) if fire else 0),fire))
