# -*- coding: utf-8 -*-
import importlib.util, statistics as st, json
spec=importlib.util.spec_from_file_location('m','bt_close_bet_mid.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
px,kospi,dates,idx,picks,bdays=m.px,m.kospi,m.dates,m.idx,m.picks,m.bdays
names=m.names; COST=m.COST
def r(c,a,b):
    x,y=px[c].get(a),px[c].get(b); return None if not x or not y else y/x-1
def kr(a,b):
    x,y=kospi.get(a),kospi.get(b); return None if not x or not y else y/x-1

def select(D,thresh,rel):
    out=[]
    p=dates[idx[D]-1]; kD=kr(p,D)
    for c in picks[D]:
        rD=r(c,p,D)
        if rD is None: continue
        if thresh is not None and not rD<thresh: continue
        if rel and not rD<kD: continue
        out.append(c)
    return out

def sim(thresh=None, rel=False, mode='v1', ds=None):
    """일별 포트폴리오 시뮬레이션. mode v1: 익일청산, v2: 재추천 지속 시 보유(중복매수 금지)"""
    bd=[d for d in bdays if (ds is None or d in ds)]
    open_pos={}     # code -> entry date
    eq=1.0; keq=1.0; daily=[]; trades=[]
    last=dates[idx[bd[-1]]+1] if idx[bd[-1]]+1<len(dates) else bd[-1]
    span=[d for d in dates if bd[0]<=d<=last]
    for t in span[1:]:
        prv=dates[idx[t]-1]
        # 전일(prv) 종가에 편입된 포지션 수익률 반영
        rs=[r(c,e_prev,t) for c,(e_prev,) in []]
        rs=[]
        for c,ent in open_pos.items():
            v=r(c,prv,t)
            if v is not None: rs.append(v)
        pr=sum(rs)/len(rs) if rs else 0.0
        eq*=1+pr; kv=kr(prv,t) or 0.0; keq*=1+kv
        daily.append((t,len(rs),pr,kv))
        # t 종가 기준 청산/신규
        if mode=='v1':
            for c,ent in list(open_pos.items()):
                v=r(c,ent,t)
                trades.append(dict(D=ent,code=c,name=names[c],exit=t,hold=idx[t]-idx[ent],r=v,rnet=v-COST,kb=kr(ent,t),open=False))
            open_pos={}
        else:
            still = set(picks.get(t,[])) if t in picks else set()
            for c,ent in list(open_pos.items()):
                if c not in still:
                    v=r(c,ent,t)
                    trades.append(dict(D=ent,code=c,name=names[c],exit=t,hold=idx[t]-idx[ent],r=v,rnet=v-COST,kb=kr(ent,t),open=False))
                    del open_pos[c]
        if t in picks and (ds is None or t in ds):
            for c in select(t,thresh,rel):
                if c not in open_pos: open_pos[c]=t
    # 잔여 포지션 평가청산
    for c,ent in open_pos.items():
        if ent==span[-1]: continue
        v=r(c,ent,span[-1])
        if v is not None:
            trades.append(dict(D=ent,code=c,name=names[c],exit=span[-1],hold=idx[span[-1]]-idx[ent],r=v,rnet=v-COST,kb=kr(ent,span[-1]),open=True))
    return dict(eq=(eq-1)*100, keq=(keq-1)*100, trades=trades, daily=daily)

def stats(res,lab):
    tr=res['trades']
    if not tr: return dict(label=lab,n=0)
    rn=[t['rnet'] for t in tr]; ex=[t['rnet']-(t['kb'] or 0) for t in tr]
    perday=[(t['rnet'])/t['hold'] for t in tr]
    return dict(label=lab,n=len(tr),mean=st.mean(rn)*100,med=st.median(rn)*100,
        win=100*sum(1 for x in rn if x>0)/len(rn), exc=st.mean(ex)*100,
        excwin=100*sum(1 for x in ex if x>0)/len(ex), perday=st.mean(perday)*100,
        hold=st.mean([t['hold'] for t in tr]), eq=res['eq'], keq=res['keq'],
        daysin=sum(1 for d in res['daily'] if d[1]>0), days=len(res['daily']))
