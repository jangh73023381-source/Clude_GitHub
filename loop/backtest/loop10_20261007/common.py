# -*- coding: utf-8 -*-
"""2026-10-07 미시도 10축 공용 — loop10_20260926 엔진 재사용. 기준 = Rule LV(mom20 pool30 → σ20 하위5), 7년, 시작 252."""
import os,sys,json,numpy as np,pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); BT=os.path.dirname(HERE)
sys.path.insert(0,os.path.join(BT,'loop10_20260926')); sys.path.insert(0,os.path.join(os.path.dirname(BT),'references','scripts'))
os.chdir(os.path.join(BT,'loop10_20260926'))
from engine import load,Engine,prof,tstat,r5,folds
S=252
def lag(X,k): return np.vstack([np.full((k,X.shape[1]),np.nan),X[:-k]])
def setup():
    P,dates,codes,names=load(os.path.join(BT,'panel_ohlc_long.csv'))
    E=Engine(P,dates,codes,names)
    base=E.run(lambda i,pl:E.sel_lv(i,pl),start=S)
    return E,base
def comp(base,name,df,res):
    m=base.merge(df,on='date',suffixes=('_b',''))
    out={}
    for k in ('A','OO'):
        d=(m[k]-m[k+'_b']).values; pb=prof(m[k+'_b']); pc=prof(m[k]); rr=r5(d)
        out[k]=dict(n=len(d),diff=float(np.nanmean(d)),t=float(tstat(d)),f=[float(x) for x in folds(d)],med=float(rr['median']),
                    drop3=float(rr['drop3']),drop10=float(rr['drop10']),cagr=pc['cagr'],mdd=pc['mdd'],sh=pc['sharpe'],
                    bcagr=pb['cagr'],bmdd=pb['mdd'],bsh=pb['sharpe'])
    res[name]=out; a,o=out['A'],out['OO']
    print(f"{name:40s} A 차{a['diff']:+.4f} t{a['t']:+.2f} f[{', '.join('%+.3f'%x for x in a['f'])}] -3일{a['drop3']:+.4f} Sh{a['sh']:.2f}({a['bsh']:.2f}) MDD{a['mdd']:.1f}({a['bmdd']:.1f}) || OO 차{o['diff']:+.4f} t{o['t']:+.2f} f[{', '.join('%+.3f'%x for x in o['f'])}] -3일{o['drop3']:+.4f} Sh{o['sh']:.2f}({o['bsh']:.2f}) MDD{o['mdd']:.1f}({o['bmdd']:.1f}) CAGR{o['cagr']:.1f}({o['bcagr']:.1f})",flush=True)
    return out
