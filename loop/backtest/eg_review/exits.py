#!/usr/bin/env python3
"""청산 규칙 비교 — 신호별 거래 수익률(진입=신호일 종가). 캐시 기반."""
import os, pickle, sys, numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
d=pickle.load(open(os.path.join(HERE,'_eg_cache.pkl'),'rb'))
C,MA20,MA60,dates=d['C'],d['MA20'],d['MA60'],d['dates']; N=len(dates); B=d['bench']
CAP=120
def exit_idx(m,t,rule):
    """반환 exit index (종가 청산일)."""
    c=C[m]; e=c[t]; hi=e
    last=min(t+CAP,N-1)
    below=0
    for j in range(t+1,last+1):
        if np.isnan(c[j]): continue
        hi=max(hi,c[j]); r=c[j]/e-1; dd=c[j]/hi-1; h=j-t
        if rule=='fix20' and h>=20: return j
        if rule=='fix40' and h>=40: return j
        if rule=='fix60' and h>=60: return j
        if rule=='ma20x' and c[j]<MA20[m,j]: return j
        if rule=='ma20x2':
            below=below+1 if c[j]<MA20[m,j] else 0
            if below>=2: return j
        if rule=='ma60x' and c[j]<MA60[m,j]: return j
        if rule=='ma20x_min20' and h>=20 and c[j]<MA20[m,j]: return j
        if rule=='ma20x2_min10':
            below=below+1 if c[j]<MA20[m,j] else 0
            if h>=10 and below>=2: return j
        if rule=='trail8' and dd<=-0.08: return j
        if rule=='trail10' and dd<=-0.10: return j
        if rule=='sl5_fix20' and (r<=-0.05 or h>=20): return j
        if rule=='sl7_fix40' and (r<=-0.07 or h>=40): return j
        if rule=='hyb': # MA20 2일 연속 이탈 또는 트레일링 -10%, 최소 5일
            below=below+1 if c[j]<MA20[m,j] else 0
            if h>=5 and (below>=2 or dd<=-0.10): return j
        if rule=='hyb60': # MA60 이탈 또는 트레일링 -12%, 최소 10일
            if h>=10 and (c[j]<MA60[m,j] or dd<=-0.12): return j
        if rule=='fix20_ma20': # 20일 보유 후 MA20 위면 계속, 이탈(2일)시 청산
            below=below+1 if c[j]<MA20[m,j] else 0
            if h>=20 and below>=2: return j
    return last
RULES=['fix20','fix40','fix60','sl5_fix20','sl7_fix40','ma20x','ma20x2','ma20x2_min10','ma20x_min20','fix20_ma20','ma60x','trail8','trail10','hyb','hyb60']
def trades(entries,rule):
    rows=[]
    for m,t in entries:
        j=exit_idx(m,t,rule)
        c=C[m]
        if np.isnan(c[j]) : 
            jj=j
            while jj>t and np.isnan(c[jj]): jj-=1
            j=jj
        r=c[j]/c[t]-1; br=B[j]/B[t]-1
        rows.append((m,t,j,j-t,r,br))
    return pd.DataFrame(rows,columns=['m','t','j','hold','ret','bench'])
if __name__=='__main__':
    eg=d['eg']; tr=d['trend']
    ent=[(m,t) for m,t in zip(*np.where(eg)) if t>=60]
    rng=np.random.default_rng(0)
    trd=[(m,t) for m,t in zip(*np.where(tr&~eg)) if t>=60]
    b1=[trd[i] for i in rng.choice(len(trd),8000,replace=False)]
    res={}
    print(f'{"rule":14s} {"n":>5s} {"mean%":>7s} {"med%":>6s} {"win%":>5s} {"hold":>5s} {"exc/B":>7s} {"perday_bp":>9s} {"B1mean%":>8s} {"vsB1":>6s} {"fold":>8s}')
    for rule in RULES:
        a=trades(ent,rule); b=trades(b1,rule)
        thirds=np.array_split(np.sort(a.t.unique()),3)
        f=[]
        for th in thirds:
            aa=a[a.t.isin(th)]; bb=b[b.t.isin(th)]
            f.append(aa.ret.mean()-bb.ret.mean())
        res[rule]=a
        print(f'{rule:14s} {len(a):5d} {a.ret.mean()*100:7.2f} {a.ret.median()*100:6.2f} {(a.ret>0).mean()*100:5.1f} {a.hold.mean():5.1f} {(a.ret-a.bench).mean()*100:7.2f} {(a.ret/a.hold).mean()*1e4:9.1f} {b.ret.mean()*100:8.2f} {(a.ret.mean()-b.ret.mean())*100:6.2f} {"/".join("+" if x>0 else "-" for x in f):>8s}')
    pickle.dump(res,open(os.path.join(HERE,'_trades.pkl'),'wb'))
