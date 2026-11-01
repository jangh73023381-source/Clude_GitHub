# -*- coding: utf-8 -*-
import sys; sys.path.insert(0,'/sessions/exciting-sharp-albattani/mnt/loop/backtest')
from bt_engine import load, universe, score, is_spot
import statistics as st
px,name,dates=load()
def mom(c,d,k):
    i=dates.index(d)
    if i<k: return None
    a=px[c].get(dates[i-k]); b=px[c].get(d)
    return (b/a-1.0) if (a and b) else None
def prevday(c,d):
    i=dates.index(d)
    if i<1: return None
    a=px[c].get(dates[i-1]); b=px[c].get(d)
    return (b/a-1.0) if (a and b) else None
def sel(d,k=5,avoid_spike_thr=None,n=5,minp=10000):
    cand=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or not is_spot(name[c]): continue
        m=mom(c,d,k)
        if m is None: continue
        if avoid_spike_thr is not None:
            r=prevday(c,d)
            if r is not None and r>=avoid_spike_thr: continue
        cand.append((c,m))
    cand.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in cand[:n]]
def run(k=5,avoid=None):
    H=[];E=[];days=0
    for i in range(max(k,5),len(dates)-1):
        d,dn=dates[i],dates[i+1]
        p=sel(d,k,avoid)
        if len(p)<5: continue
        s=score(px,name,d,dn,p)
        if not s or s['avg_excess'] is None: continue
        H.append(s['hit']); E.append(s['avg_excess']); days+=1
    return days, st.mean(H), st.mean(E)*100
print(f"{'룰':<22}{'일수':>4}{'평균적중/5':>10}{'KODEX200초과%':>13}")
for k in (3,5,10,20):
    d,h,e=run(k=k); print(f"{'모멘텀 '+str(k)+'일':<22}{d:>4}{h:>10.2f}{e:>13.2f}")
for thr in (0.10,0.15,0.20):
    d,h,e=run(k=5,avoid=thr); print(f"{'모멘텀5일+전일>'+str(int(thr*100))+'%제외':<22}{d:>4}{h:>10.2f}{e:>13.2f}")
