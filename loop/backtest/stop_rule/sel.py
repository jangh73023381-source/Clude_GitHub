# -*- coding: utf-8 -*-
import os,sys,numpy as np,pandas as pd
sys.path.insert(0,os.environ['HOME']+'/mnt/loop/references/scripts')
from universe_filters import eligible
df=pd.read_csv(os.environ['HOME']+'/mnt/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
df=df[df['name'].map(eligible)]
cl=df.pivot_table(index='date',columns='code',values='close')
cl=cl.sort_index()
dates=cl.index.to_numpy(); C=cl.to_numpy(float)
bench_code='069500'
bi=list(cl.columns).index(bench_code) if bench_code in cl.columns else None
def mom(k):
    return C/np.roll(C,k,axis=0)-1
M20=mom(20); M60=mom(60); M150=mom(150)
SIG=pd.DataFrame(C).pct_change().rolling(20).std().to_numpy()
ben=C[:,bi]; ma20=pd.Series(ben).rolling(20).mean().to_numpy(); ma60=pd.Series(ben).rolling(60).mean().to_numpy()
def run(H, rank, k=5, pool=30, lowvol=False, gate=None):
    rets=[]; i=200
    while i+H < len(dates):
        row=rank[i]; ok=np.isfinite(row)&np.isfinite(C[i])&np.isfinite(C[i+H])
        if gate=='ma20' and not (ben[i]>ma20[i]): i+=H; rets.append(0.0); continue
        if gate=='ma60' and not (ben[i]>ma60[i]): i+=H; rets.append(0.0); continue
        idx=np.where(ok)[0]
        if len(idx)<10: i+=H; continue
        order=idx[np.argsort(-row[idx])]
        if lowvol:
            p=order[:pool]; p=p[np.isfinite(SIG[i][p])]
            p=p[np.argsort(SIG[i][p])][:k]
        else:
            p=order[:k]
        rets.append(float(np.mean(C[i+H][p]/C[i][p]-1)))
        i+=H
    r=np.array(rets); 
    return r
def bh(H):
    rets=[];i=200
    while i+H<len(dates):
        rets.append(ben[i+H]/ben[i]-1); i+=H
    return np.array(rets)
print(f"{'전략':28s} {'구간수':>5s} {'구간평균':>9s} {'누적':>9s} {'승률':>6s} {'KODEX200대비':>12s}")
for H in [5,10,20,40]:
    b=bh(H)
    print(f"--- 보유 {H}거래일  (KODEX200 구간평균 {100*b.mean():+.3f}% 누적 {100*(np.prod(1+b)-1):+.1f}%)")
    for nm,kw in [('mom20 상위5',dict(rank=M20)),
                  ('mom60 상위5',dict(rank=M60)),
                  ('mom150 상위5',dict(rank=M150)),
                  ('mom20 pool30→저변동5 (LV)',dict(rank=M20,lowvol=True)),
                  ('mom150 pool30→저변동5',dict(rank=M150,lowvol=True)),
                  ('mom150 상위5 +지수MA20게이트',dict(rank=M150,gate='ma20')),
                  ('mom150 LV +지수MA60게이트',dict(rank=M150,lowvol=True,gate='ma60'))]:
        r=run(H,**kw); n=min(len(r),len(b)); d=r[:n]-b[:n]
        print(f"{nm:28s} {len(r):5d} {100*r.mean():+8.3f}% {100*(np.prod(1+r)-1):+8.1f}% {100*(r>0).mean():5.1f}% {100*d.mean():+11.3f}%p")
