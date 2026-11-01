# -*- coding: utf-8 -*-
"""진단 — 픽5 포트폴리오의 KODEX200 대비 베타·알파·추적오차·IR."""
import os, sys, csv, statistics
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import bt_iter2_3_20260729 as B
B.MINP=0
BENCH='069500'

def series(panel):
    B.PANEL=os.path.join(HERE,panel)
    px,name,dates=B.load_panel()
    di={d:i for i,d in enumerate(dates)}
    fo,ins=B.load_flow()
    out=[]
    for i in range(21,len(dates)-1):
        d,nxt=dates[i],dates[i+1]
        cand=B.build_cand(px,name,d,di,dates)
        if len(cand)<10: continue
        picks=B.base_sel(cand)
        rets=[px[c][nxt]/px[c][d]-1.0 for c in picks if px[c].get(d) and px[c].get(nxt)]
        if not rets: continue
        ba,bb=px[BENCH].get(d),px[BENCH].get(nxt)
        if not(ba and bb): continue
        out.append((d,nxt,sum(rets)/len(rets),bb/ba-1.0,picks))
    return out,px,name,dates,di

def ols(y,x):
    mx,my=statistics.mean(x),statistics.mean(y)
    sxy=sum((a-mx)*(b-my) for a,b in zip(x,y)); sxx=sum((a-mx)**2 for a in x)
    b=sxy/sxx if sxx else float('nan'); return b, my-b*mx

def mdd(cum):
    peak=-1e9; m=0
    for v in cum:
        peak=max(peak,v); m=min(m,v-peak)
    return m

for panel in ['panel_close_0813.csv']:
    s,px,name,dates,di=series(panel)
    p=[r[2] for r in s]; b=[r[3] for r in s]
    ex=[100*((a-0.0010)-c) for a,c in zip(p,b)]
    beta,alpha=ols(p,b)
    print(f'--- {panel} · n={len(s)}일 ({s[0][0]}~{s[-1][1]}) ---')
    print(f'픽5 일평균 {100*statistics.mean(p):+.4f}%  KODEX200 일평균 {100*statistics.mean(b):+.4f}%')
    print(f'픽5 일변동성 {100*statistics.stdev(p):.4f}%  KODEX200 {100*statistics.stdev(b):.4f}%')
    print(f'베타(픽5~KODEX200) = {beta:.4f}   일간알파 = {100*alpha:+.4f}%')
    print(f'평균 초과(비용후) {statistics.mean(ex):+.4f}%p/일  추적오차(일) {statistics.stdev(ex):.4f}%p')
    ir=statistics.mean(ex)/statistics.stdev(ex)
    print(f'정보비율 IR(일) {ir:+.4f}  → 연환산 {ir*(250**0.5):+.3f}')
    cum=[]; t=0.0
    for e in ex: t+=e; cum.append(t)
    print(f'누적 초과 {cum[-1]:+.2f}%p · 초과 MDD {mdd(cum):+.2f}%p')
    # 시장 상승/하락일 분해
    up=[e for e,bb in zip(ex,b) if bb>0.005]; dn=[e for e,bb in zip(ex,b) if bb<-0.005]; fl=[e for e,bb in zip(ex,b) if abs(bb)<=0.005]
    print(f'KODEX200 +0.5%초과일 n={len(up)} 평균초과 {statistics.mean(up):+.4f}%p')
    print(f'      -0.5%미만일 n={len(dn)} 평균초과 {statistics.mean(dn):+.4f}%p')
    print(f'          보합일 n={len(fl)} 평균초과 {statistics.mean(fl):+.4f}%p')
    print(f'최근 20일 평균초과 {statistics.mean(ex[-20:]):+.4f}%p · 최근 5일 {[f"{e:+.2f}" for e in ex[-5:]]}')
