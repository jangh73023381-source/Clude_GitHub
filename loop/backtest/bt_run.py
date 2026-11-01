# -*- coding: utf-8 -*-
import sys; sys.path.insert(0,'/sessions/exciting-sharp-albattani/mnt/loop/backtest')
from bt_engine import load, universe, score, is_spot, mom
import statistics as st

px,name,dates=load()

BROAD=('KODEX 200','TIGER 200','KOSEF 200','ACE 200','RISE 200','PLUS 200','KBSTAR 200','KODEX200','HANARO 200','SOL 200','1Q 200','KIWOOM 200','KODEX 코스닥150','TIGER 코스닥150','RISE 코스닥150')
def is_broad(nm): return any(b in nm for b in BROAD)

def prevday_ret(c,d):  # 단일세션 D 등락 (전일 급등 식별용; D종가 가용)
    i=dates.index(d)
    if i<1: return None
    a=px[c].get(dates[i-1]); b=px[c].get(d)
    return (b/a-1.0) if (a and b) else None

def sel(px,name,d,strat,n=5,minp=10000):
    # 후보: 현물, 전일종가>=minp, 5일모멘텀 존재
    cand=[]
    # 전일(D) 단일세션 상위10% 컷오프(테마 급등 식별)
    day=[]
    for c in px:
        pc=px[c].get(d)
        if pc and pc>=minp and is_spot(name[c]):
            r=prevday_ret(c,d)
            if r is not None: day.append((c,r))
    day.sort(key=lambda x:x[1],reverse=True)
    spike_cut=set(c for c,_ in day[:max(1,len(day)//10)])  # 전일 상위10% = 급등
    for c in px:
        pc=px[c].get(d)
        if not pc or pc<minp or not is_spot(name[c]): continue
        m=mom(px,c,d,dates,5)
        if m is None: continue
        if strat in ('mom_nobroad','ruleE') and is_broad(name[c]): continue
        if strat=='ruleE' and c in spike_cut: continue  # 전일 급등 테마 추격 배제
        cand.append((c,m))
    cand.sort(key=lambda x:x[1],reverse=True)
    return [c for c,_ in cand[:n]]

def run(strat):
    H=[];P=[];E=[];days=0
    for i in range(5,len(dates)-1):
        d,dn=dates[i],dates[i+1]
        picks=sel(px,name,d,strat)
        if len(picks)<5: continue
        s=score(px,name,d,dn,picks)
        if not s or s['avg_pct'] is None: continue
        H.append(s['hit']); P.append(s['avg_pct']); E.append(s['avg_excess']); days+=1
    if not days: return None
    return {'days':days,'mean_hit':st.mean(H),'p_ge1':sum(h>=1 for h in H)/days*100,
            'p_ge3':sum(h>=3 for h in H)/days*100,'p_eq5':sum(h==5 for h in H)/days*100,
            'mean_pct':st.mean(P),'mean_excess':st.mean(E)*100}

print(f"{'전략':<14}{'일수':>4}{'평균적중/5':>10}{'≥1적중%':>9}{'≥3적중%':>9}{'5/5%':>7}{'평균백분위':>10}{'KODEX200초과%':>13}")
for s in ['mom','mom_nobroad','ruleE']:
    r=run(s)
    label={'mom':'모멘텀top5','mom_nobroad':'모멘텀(지수제외)','ruleE':'RuleE(급등회피)'}[s]
    print(f"{label:<14}{r['days']:>4}{r['mean_hit']:>10.2f}{r['p_ge1']:>9.1f}{r['p_ge3']:>9.1f}{r['p_eq5']:>7.1f}{r['mean_pct']:>10.1f}{r['mean_excess']:>13.2f}")
# 참조: 무작위 기대 적중률 = 10% (상위10% 정의상). 5종 평균 백분위 50 = 시장중립.
