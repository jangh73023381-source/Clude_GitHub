# -*- coding: utf-8 -*-
"""핵심 검증 — '저항선 바로 아래 밴드(pos 0.80~0.95)' 종목만 매수, 없으면 현금 관망.
5종 강제 충원을 없애면 bin 통계(+0.18~0.24%)가 실제 전략 수익으로 전환되는가?
비교군: 5종 강제(POS-BAND), mom20 baseline, 밴드 밖 매수(플라시보)."""
import os, sys, statistics, math
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from channel_engine import load, Channel, BENCH, LOOKBACKS, LB_LABEL
import bt_channel as BC

HERE=os.path.dirname(os.path.abspath(__file__)); COST=0.0010
bars, meta, dates, codes = load(os.path.join(HERE,'ohlc_stock15.csv'))
C = Channel(bars, dates, codes)

def run_band(N, lo, hi, maxn=None, invert=False, use_rh=True):
    xs=[]; nbuy=[]; cash=0
    for i in range(BC.START, len(dates)-1):
        d, dn = dates[i], dates[i+1]
        a,b = C.close(BENCH,d), C.close(BENCH,dn)
        if not (a and b): continue
        bm = b/a-1.0
        picks=[]
        for c in codes:
            if use_rh and not BC.rule_h_ok(C,c,d): continue
            v = C.pos(c,d,N)
            if v is None: continue
            inb = lo <= v <= hi
            if inb != invert: picks.append((c, C.mom(c,d,20) or 0))
        if maxn:
            picks.sort(key=lambda x:x[1], reverse=True); picks=picks[:maxn]
        if not picks:
            cash+=1; xs.append(0.0 - bm); nbuy.append(0); continue
        rs=[]
        for c,_ in picks:
            x,y = C.close(c,d), C.close(c,dn)
            if x and y: rs.append(y/x-1.0)
        if not rs:
            cash+=1; xs.append(-bm); nbuy.append(0); continue
        xs.append(sum(rs)/len(rs) - COST - bm); nbuy.append(len(rs))
    return xs, statistics.mean(nbuy), cash

def mom_base():
    xs=[]
    for i in range(BC.START, len(dates)-1):
        d,dn=dates[i],dates[i+1]
        a,b=C.close(BENCH,d),C.close(BENCH,dn)
        if not (a and b): continue
        bm=b/a-1.0
        p=BC.select(C,codes,d,None)
        rs=[C.close(c,dn)/C.close(c,d)-1.0 for c in p if C.close(c,d) and C.close(c,dn)]
        xs.append(sum(rs)/len(rs)-COST-bm)
    return xs

base=mom_base(); half=len(base)//2
def cum(xs): 
    v=1.0
    for x in xs: v*=(1+x)
    return (v-1)*100
print('='*100)
print(f'채점 {len(base)}일 | baseline mom20: 일평균 {statistics.mean(base)*100:+.4f}%, 누적초과 {cum(base):+.1f}%')
print('='*100)
print(f"{'전략':40s}{'일평균%':>9s}{'누적초과%':>11s}{'train':>9s}{'test':>9s}{'평균매수':>9s}{'관망일':>7s}{'t':>7s}")
print('-'*100)
rows=[]
for N in LOOKBACKS:
    for lo,hi,tag in [(0.80,0.95,'0.80~0.95'),(0.70,1.00,'0.70~1.00'),(0.85,1.00,'0.85~1.00')]:
        xs,avn,cash = run_band(N,lo,hi)
        m,t,p = BC.paired_t(xs, base[:len(xs)])
        h=len(xs)//2
        rows.append((statistics.mean(xs), f'밴드매수 {tag} / {LB_LABEL[N]}', xs, avn, cash, t))
        print(f"{('밴드매수 '+tag+' / '+LB_LABEL[N]):40s}{statistics.mean(xs)*100:>9.4f}{cum(xs):>11.1f}"
              f"{statistics.mean(xs[:h])*100:>9.4f}{statistics.mean(xs[h:])*100:>9.4f}{avn:>9.2f}{cash:>7d}{t:>7.2f}")
print('-'*100)
# 플라시보: 밴드 밖 매수
for N in [120,250]:
    xs,avn,cash = run_band(N,0.80,0.95,invert=True)
    h=len(xs)//2
    print(f"{('[플라시보] 밴드밖 매수 / '+LB_LABEL[N]):40s}{statistics.mean(xs)*100:>9.4f}{cum(xs):>11.1f}"
          f"{statistics.mean(xs[:h])*100:>9.4f}{statistics.mean(xs[h:])*100:>9.4f}{avn:>9.2f}{cash:>7d}")
# 5종 강제 비교
print('-'*100)
for N in [120,250]:
    xs,avn,cash = run_band(N,0.80,0.95,maxn=5)
    h=len(xs)//2
    print(f"{('[5종상한] 밴드매수 / '+LB_LABEL[N]):40s}{statistics.mean(xs)*100:>9.4f}{cum(xs):>11.1f}"
          f"{statistics.mean(xs[:h])*100:>9.4f}{statistics.mean(xs[h:])*100:>9.4f}{avn:>9.2f}{cash:>7d}")
print(f"{'baseline mom20 top5':40s}{statistics.mean(base)*100:>9.4f}{cum(base):>11.1f}"
      f"{statistics.mean(base[:half])*100:>9.4f}{statistics.mean(base[half:])*100:>9.4f}{5.0:>9.2f}{0:>7d}")
