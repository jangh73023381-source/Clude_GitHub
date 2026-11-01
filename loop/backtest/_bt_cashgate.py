#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rule O backtest: gate-gated capital-preservation cash-proxy tilt.
Look-ahead-free: selection uses info <= day D close; score = day D+1 close.
Gate proxy computable at D close (index return on day D). If gate active,
replace the 2 lowest-mom20 slots of the mom20+RuleH top5 with the 2 largest
cash-proxy ETFs (static liquidity rank). Compare vs baseline (mom20+RuleH).
"""
import csv, math, statistics
base='/sessions/funny-stoic-heisenberg/mnt/loop'

# load panel
panel={}; names={}
for r in csv.DictReader(open(base+'/panel_close.csv',encoding='utf-8')):
    c=r['code']; panel.setdefault(c,{})[r['date']]=float(r['close'])
    if r['name']: names[c]=r['name']
dates=sorted({d for dd in panel.values() for d in dd})

# static liquidity (거래대금) from etf_universe.csv
liq={}
for r in csv.DictReader(open(base+'/etf_universe.csv',encoding='utf-8-sig')):
    try: liq[r['티커'].strip()]=float(r['거래대금'])
    except: pass

def excl(nm):
    n=(nm or '').replace(' ','')
    return ('레버리지' in n or '2X' in n.upper() or '인버스' in n or '곱버스' in n or '숏' in n)

CASH_KW=['머니마켓','MMF','CD금리','CD1년','KOFR','초단기채','금리투자','금리플러스액티브','금리액티브']
def is_cash(nm):
    n=(nm or '').replace(' ','')
    return any(k in n for k in CASH_KW)

cash_codes=sorted([c for c in panel if is_cash(names.get(c,'')) and not excl(names.get(c,''))],
                  key=lambda c:-liq.get(c,0))
print('cash-proxy codes in panel:',len(cash_codes))
for c in cash_codes[:8]: print('  ',c,names.get(c,'')[:26],'거래대금',int(liq.get(c,0)))

IDX='069500'  # KODEX 200 as market proxy

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
    cand.sort(key=lambda x:x[1],reverse=True)
    return cand[:5]

def ret(c,di):
    D=dates[di]; N=dates[di+1]
    a=panel[c].get(D); b=panel[c].get(N)
    return (b/a-1) if (a and b) else None

def hits(picks,di):
    D=dates[di]; N=dates[di+1]
    uni=[]
    for c,dd in panel.items():
        if '숏' in names.get(c,''): continue
        pc=dd.get(D); nc=dd.get(N)
        if not pc or not nc or pc<10000: continue
        uni.append((c,nc/pc-1))
    uni.sort(key=lambda x:x[1],reverse=True)
    Nn=len(uni); cut=max(1,math.ceil(Nn*0.10))
    top=set(c for c,_ in uni[:cut])
    return sum(1 for c in picks if c in top), Nn, cut

def gate_active(di, thr):
    D=dates[di]; d1=dates[di-1]
    px=panel.get(IDX,{}).get(D); px1=panel.get(IDX,{}).get(d1)
    if not px or not px1: return False, None
    r=px/px1-1
    return (r<=thr), r

def rule_o(di, gate):
    base5=mom20_ruleh(di)
    if not gate: return [c for c,_ in base5], False
    codes=[c for c,_ in base5]
    # available cash proxies with valid prev price
    D=dates[di]
    avail=[c for c in cash_codes if panel[c].get(D,0)>=10000]
    repl=avail[:2]
    if len(repl)<2: return codes, False
    # replace 2 lowest-mom20 (last 2 of sorted base5) that are not already cash
    keep=[c for c,_ in base5][:3]
    newp=keep+repl
    return newp[:5], True

for GATE_THR in (-0.02,-0.015,-0.025):
    days=[i for i in range(21,len(dates)-1)]
    b_hits=[]; o_hits=[]; fire=[]
    b_fire=[]; o_fire=[]
    for di in days:
        gate,gr=gate_active(di,GATE_THR)
        bp=[c for c,_ in mom20_ruleh(di)]
        op,fired=rule_o(di,gate)
        bh,_,_=hits(bp,di); oh,_,_=hits(op,di)
        b_hits.append(bh); o_hits.append(oh)
        if fired:
            fire.append(dates[di]); b_fire.append(bh); o_fire.append(oh)
    n=len(b_hits)
    print('\n=== GATE_THR %.1f%% (index %s day-D ret) ==='%(GATE_THR*100,IDX))
    print('scoring days: %d'%n)
    print('  baseline avg hits/5 = %.3f'%(sum(b_hits)/n))
    print('  ruleO    avg hits/5 = %.3f'%(sum(o_hits)/n))
    print('  gate-fire days: %d  %s'%(len(fire),fire))
    if fire:
        print('  on fire days: baseline %.3f -> ruleO %.3f'%(sum(b_fire)/len(fire),sum(o_fire)/len(fire)))
        print('  fire-day detail (date, base->ruleO):')
        for d,b,o in zip(fire,b_fire,o_fire): print('     %s %d -> %d'%(d,b,o))
