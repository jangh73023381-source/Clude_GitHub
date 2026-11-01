# -*- coding: utf-8 -*-
"""회전율 인지 비용 모형으로 보유기간 축 재검정.

기존 하네스는 매일 flat 10bp 를 부과한다. 그러나 실측 일일 교체율은 26~31%다.
→ baseline 은 실제보다 약 7bp/일 과다 과금돼 왔다.

여기서는 H일 보유를 'H개 중첩 트랜치(매일 1/H 롤)'로 시뮬레이션하고,
비용 = 0.0010 × (일별 단방향 교체 비중) 으로 부과한다. H=1 이면 기존 정의와
100% 교체 시 정확히 일치한다.
"""
import os,sys,statistics,csv
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import bt_iter2_3_20260729 as B
from bt_hold import load2y,jk
B.MINP=0; BENCH='069500'

def sim(px,name,dates,di,H,cost_rate=0.0010,turnover_aware=True):
    """H개 중첩 트랜치. 반환: (일별 초과 %p 리스트, 평균 일일 교체율)"""
    picks_by_day={}
    for i in range(21,len(dates)-1):
        cand=B.build_cand(px,name,dates[i],di,dates)
        if len(cand)<10: continue
        picks_by_day[i]=B.base_sel(cand)
    idx=sorted(picks_by_day)
    recs=[]; turns=[]; prevw=None
    for i in idx:
        if i-(H-1) < idx[0]: continue
        # 보유 = 최근 H개 선정일의 픽을 1/H 씩
        w=defaultdict(float); ok=True
        for h in range(H):
            j=i-h
            if j not in picks_by_day: ok=False; break
            for c in picks_by_day[j]: w[c]+=1.0/(H*5)
        if not ok: continue
        d,nxt=dates[i],dates[i+1]
        # 당일 종가 → 익일 종가 수익
        r=0.0; tot=0.0
        for c,ww in w.items():
            a,b=px[c].get(d),px[c].get(nxt)
            if a and b: r+=ww*(b/a-1.0); tot+=ww
        if tot<0.99: continue
        ba,bb=px[BENCH].get(d),px[BENCH].get(nxt)
        if not(ba and bb): continue
        if prevw is None: t=1.0
        else:
            keys=set(w)|set(prevw)
            t=sum(max(0.0,w.get(k,0)-prevw.get(k,0)) for k in keys)
        turns.append(t)
        c_=cost_rate*t if turnover_aware else cost_rate
        recs.append(100*((r-c_)-(bb/ba-1.0)))
        prevw=dict(w)
    return recs,(statistics.mean(turns[1:]) if len(turns)>1 else float('nan'))

if __name__=='__main__':
    for tag,loader in [('2년 패널',load2y)]:
        if tag.startswith('2년'): px,name,dates=loader()
        di={d:i for i,d in enumerate(dates)}
        print(f'=== 회전율 인지 비용 · {tag} ({dates[0]}~{dates[-1]}) ===')
        print(f"{'H':>4s} {'n':>5s} {'교체율':>8s} {'전체':>9s} {'train':>9s} {'test':>9s} {'잭나이프':>9s} {'IR':>8s}")
        print('-'*76)
        base=None
        for H in (1,2,3,5,7,10):
            r,t=sim(px,name,dates,di,H)
            if not r: continue
            h=len(r)//2
            f,t1,t2=statistics.mean(r),statistics.mean(r[:h]),statistics.mean(r[h:])
            s=statistics.stdev(r)
            mark=''
            if base is None: base=(f,t1,t2); mark='← 신 기준선'
            elif f>base[0] and t1>base[1] and t2>base[2]:
                mark=' ✓3분할' + (' +잭나이프' if jk(r)>base[0] else '')
            print(f'{H:4d} {len(r):5d} {t:8.1%} {f:+9.4f} {t1:+9.4f} {t2:+9.4f} {jk(r):+9.4f} {f/s:+8.4f} {mark}')

        print(f'\n[대조] 동일 H를 flat 10bp/일로 과금하면 (기존 하네스 정의)')
        print(f"{'H':>4s} {'전체':>9s}  차이(%p/일)")
        for H in (1,3,5):
            ra,_=sim(px,name,dates,di,H)
            rb,_=sim(px,name,dates,di,H,turnover_aware=False)
            print(f'{H:4d} {statistics.mean(rb):+9.4f}  {statistics.mean(ra)-statistics.mean(rb):+.4f}')
