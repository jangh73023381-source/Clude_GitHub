# -*- coding: utf-8 -*-
"""중기 ETF 종가베팅 백테스트 v3 — 비용(편도 5bp) 반영 일별 포트폴리오 + 거래별 통계"""
import importlib.util, statistics as st
spec=importlib.util.spec_from_file_location('m','/sessions/zealous-laughing-mccarthy/mnt/loop/backtest/bt_close_bet_mid.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
px,kospi,dates,idx,picks,bdays,names=m.px,m.kospi,m.dates,m.idx,m.picks,m.bdays,m.names
ONEWAY=0.0005
def r(c,a,b):
    x,y=px[c].get(a),px[c].get(b); return None if not x or not y else y/x-1
def kr(a,b):
    x,y=kospi.get(a),kospi.get(b); return None if not x or not y else y/x-1
def kodex(a,b): return r('069500',a,b)
def select(D,thresh,rel,exclude_up=None):
    p=dates[idx[D]-1]; kD=kr(p,D); out=[]
    for c in picks[D]:
        rD=r(c,p,D)
        if rD is None: continue
        if thresh is not None and not rD<thresh: continue
        if rel and not rD<kD: continue
        out.append(c)
    return out
def sim(thresh=None, rel=False, mode='v1', drop=None):
    bd=[d for d in bdays if drop is None or d!=drop]
    span=[d for d in dates if bd[0]<=d<=dates[-1]]
    held={}; eq=1.0; keq=1.0; kdeq=1.0; daily=[]; trades=[]
    for t in span[1:]:
        prv=dates[idx[t]-1]
        rs=[r(c,prv,t) for c in held if r(c,prv,t) is not None]
        gross=sum(rs)/len(rs) if rs else 0.0
        old=set(held)
        # t 종가에 청산/신규 결정
        if mode=='v1': keep=set()
        else: keep=set(c for c in held if c in set(picks.get(t,[])))
        new=set(select(t,thresh,rel)) if (t in picks and t in bd) else set()
        for c in list(held):
            if c not in keep:
                v=r(c,held[c],t)
                if v is not None and idx[t]>idx[held[c]]:
                    trades.append(dict(D=held[c],code=c,name=names[c],exit=t,hold=idx[t]-idx[held[c]],
                        r=v, rnet=v-2*ONEWAY, kb=kr(held[c],t), kd=kodex(held[c],t)))
                del held[c]
        for c in new:
            if c not in held: held[c]=t
        # 회전 비용: 편도 5bp × (매도비중+매수비중)
        sold=len(old-keep)/max(len(old),1) if old else 0.0
        bought=len([c for c in held if held[c]==t])/max(len(held),1) if held else 0.0
        cost=ONEWAY*(sold+bought)
        net=gross-cost
        eq*=1+net; kv=kr(prv,t) or 0.0; keq*=1+kv; kd=kodex(prv,t) or 0.0; kdeq*=1+kd
        daily.append((t,len(rs),gross,net,kv))
    for c,ent in held.items():
        v=r(c,ent,dates[-1])
        if v is not None and idx[dates[-1]]>idx[ent]:
            trades.append(dict(D=ent,code=c,name=names[c],exit=dates[-1],hold=idx[dates[-1]]-idx[ent],
                r=v,rnet=v-2*ONEWAY,kb=kr(ent,dates[-1]),kd=kodex(ent,dates[-1])))
    return dict(eq=(eq-1)*100,keq=(keq-1)*100,kdeq=(kdeq-1)*100,trades=trades,daily=daily)
def stats(res,lab=''):
    tr=res['trades']
    if not tr: return dict(label=lab,n=0)
    rn=[t['rnet'] for t in tr]; ex=[t['rnet']-(t['kb'] or 0) for t in tr]
    exd=[t['rnet']-(t['kd'] or 0) for t in tr]
    return dict(label=lab,n=len(tr),mean=st.mean(rn)*100,med=st.median(rn)*100,
        win=100*sum(1 for x in rn if x>0)/len(rn),exc=st.mean(ex)*100,
        excwin=100*sum(1 for x in ex if x>0)/len(ex),excd=st.mean(exd)*100,
        perday=st.mean([t['rnet']/t['hold'] for t in tr])*100,
        hold=st.mean([t['hold'] for t in tr]),eq=res['eq'],keq=res['keq'],kdeq=res['kdeq'],
        daysin=sum(1 for d in res['daily'] if d[1]>0),days=len(res['daily']))
