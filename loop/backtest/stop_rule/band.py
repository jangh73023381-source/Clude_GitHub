# -*- coding: utf-8 -*-
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.environ['HOME']+'/mnt/loop/references/scripts')
from universe_filters import eligible
df = pd.read_csv(os.environ['HOME']+'/mnt/loop/backtest/panel_ohlc_long.csv', dtype={'code':str})
df = df[df['name'].map(eligible)].sort_values(['code','date'])
H = 20
BANDS = [0.005,0.01,0.02,0.03,0.05]
ATRK  = [1.0,1.5,2.0]
res = {k:[] for k in ['bh']+[f'b{b}' for b in BANDS]+[f'a{k}' for k in ATRK]}
for code, g in df.groupby('code', sort=False):
    if len(g) < 80: continue
    o=g['open'].to_numpy(float); h=g['high'].to_numpy(float)
    l=g['low'].to_numpy(float);  c=g['close'].to_numpy(float)
    n=len(c); m=n-H
    if m<=0: continue
    pc=np.r_[c[0],c[:-1]]
    tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    atr=pd.Series(tr).rolling(14).mean().to_numpy()
    C0=c[:m]; CH=c[H:H+m]
    res['bh'].append(CH/C0)
    specs=[(f'b{b}', C0*0 + b, None) for b in BANDS]+[(f'a{k}', None, k) for k in ATRK]
    for key,bandarr,k in specs:
        if k is not None:
            a0=atr[:m]
            frac=np.where(np.isfinite(a0), k*a0/C0, np.nan)
        else:
            frac=bandarr
        peak=C0.copy(); done=np.zeros(m,bool); fill=np.zeros(m)
        for t in range(1,H+1):
            hi=h[t:t+m]; lo=l[t:t+m]; op=o[t:t+m]
            peak=np.maximum(peak,hi)
            stop=peak*(1-frac)
            hit=(~done)&(lo<=stop)&np.isfinite(stop)
            if hit.any():
                f=np.where(op<stop,op,stop)
                fill[hit]=f[hit]; done[hit]=True
        r=np.where(done,0.5*(fill/C0)+0.5*(CH/C0),CH/C0)
        r=np.where(np.isfinite(frac),r,np.nan)
        res[key].append(r)
tab={k:np.concatenate(v) for k,v in res.items()}
bh=tab['bh']
print(f"n={len(bh):,}  방치 평균 {100*(bh.mean()-1):+.4f}%  하위5% {100*(np.percentile(bh,5)-1):+.2f}%  하위1% {100*(np.percentile(bh,1)-1):+.2f}%  표준편차 {100*bh.std():.2f}%")
for k in tab:
    if k=='bh': continue
    r=tab[k]; ok=np.isfinite(r)
    d=r[ok]-bh[ok]
    lab = k[1:]+('%' if k[0]=='b' else ' ATR')
    lab = (f"고정 {float(k[1:])*100:.1f}%" if k[0]=='b' else f"{float(k[1:]):.1f}×ATR14")
    print(f"{lab:12s} 발동후반절매도 평균 {100*(r[ok].mean()-1):+.4f}%  방치대비 {100*d.mean():+.4f}%p  하위5% {100*(np.percentile(r[ok],5)-1):+.2f}%  하위1% {100*(np.percentile(r[ok],1)-1):+.2f}%  변동성 {100*r[ok].std():.2f}%")
