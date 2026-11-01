# -*- coding: utf-8 -*-
"""연속 채점 백테스트 엔진. 룩어헤드 금지: 선정은 D종가까지 정보만, 채점은 D+1.
지표: 적중수(0~5,상위10%), 평균백분위(0=최상위), KODEX200 대비 초과수익, D+1·D+2."""
import csv, math
from collections import defaultdict

BASE='/sessions/exciting-sharp-albattani/mnt/loop'
BENCH='069500'  # KODEX 200

def load():
    px=defaultdict(dict); name={}
    for r in csv.DictReader(open(BASE+'/backtest/prices_long.csv',encoding='utf-8')):
        try: px[r['code']][r['date']]=float(r['close'])
        except: pass
        name[r['code']]=r['name']
    dates=sorted({d for c in px for d in px[c]})
    return px,name,dates

def is_short(nm):
    # 숏선물(숏 방향성) 상품. '은선물/골드선물'은 '숏' 미포함이라 대상 아님. (2026-07-06 사용자 지시)
    return '숏' in nm.replace(' ','')

def is_spot(nm):
    n=nm.replace(' ','')
    return not('인버스' in n or '곱버스' in n or '레버리지' in n or '2X' in n.upper() or '2배' in n or '숏' in n)

def universe(px,name,d,dnext,minp=10000):
    # 채점 유니버스: 숏선물은 제외(2026-07-06). 레버리지·인버스는 기존 관행대로 채점 유니버스에 포함.
    u=[]
    for c in px:
        if is_short(name.get(c,'')): continue
        pc=px[c].get(d); nc=px[c].get(dnext)
        if pc and nc and pc>=minp:
            u.append((c,pc,nc,nc/pc-1.0))
    return u

def score(px,name,d,dnext,picks):
    u=universe(px,name,d,dnext)
    if not u: return None
    u.sort(key=lambda x:x[3],reverse=True)
    N=len(u); cutoff=max(1,math.ceil(N*0.10))
    rank={c:i+1 for i,(c,_,_,_) in enumerate(u)}
    ret={c:r for c,_,_,r in u}
    bench=ret.get(BENCH,0.0)
    hit=0; pcts=[]; exrs=[]
    for c in picks:
        if c in rank:
            rk=rank[c]; hit+= 1 if rk<=cutoff else 0
            pcts.append((rk-1)/N*100); exrs.append(ret[c]-bench)
    return {'N':N,'cutoff':cutoff,'hit':hit,'npick':len(picks),
            'avg_pct': sum(pcts)/len(pcts) if pcts else None,
            'avg_excess': sum(exrs)/len(exrs) if exrs else None}

# ---- 기계적 선정룰들 (룩어헤드 금지: D종가까지 정보만) ----
def mom(px,c,d,dates,k=5):
    i=dates.index(d)
    if i<k: return None
    d0=dates[i-k]; a=px[c].get(d0); b=px[c].get(d)
    return (b/a-1.0) if (a and b) else None

def sel_momentum(px,name,d,dates,minp=10000,n=5):
    cand=[]
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or not is_spot(name[c]): continue
        m=mom(px,c,d,dates,5)
        if m is not None: cand.append((c,m))
    cand.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in cand[:n]]

if __name__=='__main__':
    px,name,dates=load()
    print('codes',len(px),'days',len(dates),dates[0],'~',dates[-1])
