import sys, numpy as np, pandas as pd
sys.path.insert(0,'/home/claude/w/loop/backtest/loop10_20260926')
from engine import load, Engine, prof, tstat, r5, folds, fmt
P,dates,codes,names=load('/home/claude/w/loop/backtest/panel_ohlc_long.csv')
E=Engine(P,dates,codes,names)
SEED=20260929
def sbb_idx(n, B=2000, L=20, seed=SEED):
    rng=np.random.default_rng(seed); p=1.0/L
    new=rng.random((B,n))<p; new[:,0]=True
    st=rng.integers(0,n,(B,n))
    t=np.arange(n)[None,:].repeat(B,0)
    pos=np.where(new,t,0); pos=np.maximum.accumulate(pos,axis=1)
    v=np.take_along_axis(st,pos,1)
    return (v+t-pos)%n
def sh(x,axis=-1):
    return x.mean(axis)/x.std(axis,ddof=1)*252**.5
def ci_shdiff(a,b,B=2000):
    a=np.asarray(a,float); b=np.asarray(b,float); m=~(np.isnan(a)|np.isnan(b)); a,b=a[m],b[m]
    I=sbb_idx(len(a),B)
    d=sh(a[I])-sh(b[I])
    return sh(a)-sh(b), np.quantile(d,[.05,.95])
def ci_mean(d,B=2000):
    d=np.asarray(d,float); d=d[~np.isnan(d)]; I=sbb_idx(len(d),B)
    return d.mean(), np.quantile(d[I].mean(1),[.05,.95])
