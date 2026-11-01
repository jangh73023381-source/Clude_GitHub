# -*- coding: utf-8 -*-
"""[6-3] 청산 규칙 3종 비교 — 7년 패널 재구성(mom150 상위5)."""
import os,sys,numpy as np,pandas as pd
sys.path.insert(0,os.environ['HOME']+'/mnt/loop/references/scripts')
from universe_filters import eligible
df=pd.read_csv(os.environ['HOME']+'/mnt/loop/backtest/panel_ohlc_long.csv',dtype={'code':str})
df=df[df['name'].map(eligible)]
cl=df.pivot_table(index='date',columns='code',values='close').sort_index()
codes=list(cl.columns); C=cl.to_numpy(float); n,m=C.shape
ben=C[:,codes.index('069500')]
M150=C/np.roll(C,150,axis=0)-1
TOP={}
for i in range(150,n):
    row=M150[i]; ok=np.isfinite(row)&np.isfinite(C[i])
    idx=np.where(ok)[0]
    TOP[i]=set(idx[np.argsort(-row[idx])][:5]) if len(idx)>=20 else set()
START=200
def sim(mode, EXTRA=20, FIX=20):
    """mode: cb=탈락 즉시 청산 / fix=진입 후 20일 고정 / reset=탈락 후 EXTRA일 더 보유"""
    hold={}   # code -> 남은일수(None=조건부)
    rets=[]; hold_lens=[]; entry={}
    for i in range(START,n-1):
        t=TOP.get(i,set())
        # --- 청산 판정 (i 종가 기준)
        for c in list(hold):
            if mode=='cb':
                if c not in t: hold_lens.append(i-entry[c]); del hold[c]
            elif mode=='fix':
                if i-entry[c]>=FIX: hold_lens.append(i-entry[c]); del hold[c]
            else: # reset
                if c in t: hold[c]=EXTRA
                else:
                    hold[c]-=1
                    if hold[c]<=0: hold_lens.append(i-entry[c]); del hold[c]
        # --- 신규 편입
        for c in t:
            if c not in hold:
                hold[c]=EXTRA; entry[c]=i
        cur=[c for c in hold if np.isfinite(C[i][c]) and np.isfinite(C[i+1][c])]
        rets.append(float(np.mean(C[i+1][cur]/C[i][cur]-1)) if cur else 0.0)
    return np.array(rets), np.array(hold_lens)
b=np.array([ben[i+1]/ben[i]-1 for i in range(START,n-1)])
def stat(nm,r,hl=None):
    eq=np.cumprod(1+r); mdd=float((eq/np.maximum.accumulate(eq)-1).min())
    sh=r.mean()/r.std()*np.sqrt(252)
    d=r-b; f=np.array_split(d,3)
    print(f"{nm:26s} 누적 {100*(eq[-1]-1):+8.1f}%  MDD {100*mdd:7.1f}%  Sharpe {sh:5.2f}  "
          f"일평균초과 {100*d.mean():+.4f}%p  3분할 {'/'.join(f'{100*x.mean():+.3f}' for x in f)}"
          + (f"  평균보유 {hl.mean():.1f}일(중앙 {np.median(hl):.0f})" if hl is not None and len(hl) else ""))
eqb=np.cumprod(1+b); mddb=float((eqb/np.maximum.accumulate(eqb)-1).min())
print(f"{'KODEX200 상시보유':26s} 누적 {100*(eqb[-1]-1):+8.1f}%  MDD {100*mddb:7.1f}%  Sharpe {b.mean()/b.std()*np.sqrt(252):5.2f}")
for nm,mode,kw in [('① 탈락 즉시 청산(현행 CB)','cb',{}),
                   ('② 진입 후 20일 고정','fix',{}),
                   ('③ 재추천 리셋+탈락후 20일','reset',{'EXTRA':20}),
                   ('③b 재추천 리셋+탈락후 10일','reset',{'EXTRA':10}),
                   ('③c 재추천 리셋+탈락후 5일','reset',{'EXTRA':5}),
                   ('③d 재추천 리셋+탈락후 1일','reset',{'EXTRA':1})]:
    r,hl=sim(mode,**kw); stat(nm,r,hl)
