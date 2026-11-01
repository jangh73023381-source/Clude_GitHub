#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Iteration 3 distinct axis: low-volatility cross-sectional tilt (general rule, not gate-conditioned).
score = w*mom20_pctile + (1-w)*lowvol_pctile  (lowvol = inverse 20d realized vol).
Compare vs baseline mom20+RuleH. train/test split (first half / second half of scoring days)."""
import csv, math, statistics
base='/sessions/funny-stoic-heisenberg/mnt/loop'
panel={}; names={}
for r in csv.DictReader(open(base+'/panel_close.csv',encoding='utf-8')):
    c=r['code']; panel.setdefault(c,{})[r['date']]=float(r['close'])
    if r['name']: names[c]=r['name']
dates=sorted({d for dd in panel.values() for d in dd})
def excl(nm):
    n=(nm or '').replace(' ','')
    return ('레버리지' in n or '2X' in n.upper() or '인버스' in n or '곱버스' in n or '숏' in n)
def cand_feats(di):
    D=dates[di]; d20=dates[di-20]; d1=dates[di-1]; d3=dates[di-3]
    out=[]
    for c,dd in panel.items():
        if excl(names.get(c,'')): continue
        pc=dd.get(D); p20=dd.get(d20)
        if not pc or not p20 or pc<10000: continue
        sess=(pc/dd[d1]-1) if dd.get(d1) else 0
        cum3=(pc/dd[d3]-1) if dd.get(d3) else 0
        if sess>0.10 or cum3>0.20: continue
        # 20d realized vol of daily returns
        rets=[]
        for k in range(di-19,di+1):
            a=dd.get(dates[k]); b=dd.get(dates[k-1])
            if a and b: rets.append(a/b-1)
        vol=statistics.pstdev(rets) if len(rets)>5 else 1.0
        out.append([c,pc/p20-1,vol])
    return out
def pct(vals):
    s=sorted(vals); n=len(s)
    return {v:i/(n-1) for i,v in enumerate(s)} if n>1 else {vals[0]:0.5}
def hits(picks,di):
    D=dates[di]; N=dates[di+1]; uni=[]
    for c,dd in panel.items():
        if '숏' in names.get(c,''): continue
        pc=dd.get(D); nc=dd.get(N)
        if not pc or not nc or pc<10000: continue
        uni.append((c,nc/pc-1))
    uni.sort(key=lambda x:x[1],reverse=True); Nn=len(uni); cut=max(1,math.ceil(Nn*0.10))
    top=set(c for c,_ in uni[:cut]); return sum(1 for c in picks if c in top)
days=[i for i in range(22,len(dates)-1)]
half=len(days)//2
def run(w):
    h=[]
    for di in days:
        f=cand_feats(di)
        moms=[x[1] for x in f]; vols=[-x[2] for x in f]  # -vol so higher=lower vol
        pm=pct(moms); pv=pct(vols)
        scored=[(x[0], w*pm[x[1]]+(1-w)*pv[-x[2]]) for x in f]
        scored.sort(key=lambda x:x[1],reverse=True)
        h.append(hits([c for c,_ in scored[:5]],di))
    return h
bh=run(1.0)  # w=1 -> pure mom20+RuleH baseline
print('baseline (w=1.0) overall %.3f  train %.3f test %.3f'%(sum(bh)/len(bh),sum(bh[:half])/half,sum(bh[half:])/(len(bh)-half)))
for w in (0.8,0.6,0.5,0.3,0.0):
    h=run(w)
    print('w_mom=%.1f  overall %.3f  train %.3f  test %.3f'%(w,sum(h)/len(h),sum(h[:half])/half,sum(h[half:])/(len(h)-half)))
