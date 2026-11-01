# -*- coding: utf-8 -*-
"""보유기간(회전주기) 축 — 루프가 한 번도 건드리지 않은 노브.
1일 회전은 왕복 10bp를 매일 낸다. 알파가 +0.133%/일인데 비용이 0.10%/일이면
비용이 알파의 75%를 먹는다. H일 보유 시 일당 비용은 10bp/H 로 준다.
중첩(overlapping) 표본이므로 t는 참고용, 잭나이프는 연속 폴드로 계산한다."""
import os,sys,statistics,csv
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import bt_iter2_3_20260729 as B
B.MINP=0; BENCH='069500'

def load2y():
    px,name=defaultdict(dict),{}
    for r in csv.DictReader(open(os.path.join(HERE,'panel_ohlc_2y.csv'),encoding='utf-8')):
        try: px[r['code']][r['date']]=float(r['close'])
        except (ValueError,KeyError,TypeError): continue
        name[r['code']]=r['name']
    return px,name,sorted({d for c in px for d in px[c]})

def jk(recs,folds=5):
    n=len(recs)
    if n<folds*3: return None
    w=n//folds; out=[]
    for f in range(folds):
        rest=recs[:f*w]+recs[(f+1)*w if f<folds-1 else n:]
        if rest: out.append(statistics.mean(rest))
    return min(out)

def run_hold(px,name,dates,di,H,cost=0.0010):
    recs=[]
    for i in range(21,len(dates)-H):
        d,ex=dates[i],dates[i+H]
        cand=B.build_cand(px,name,d,di,dates)
        if len(cand)<10: continue
        picks=B.base_sel(cand)
        rets=[px[c][ex]/px[c][d]-1.0 for c in picks if px[c].get(d) and px[c].get(ex)]
        if not rets: continue
        ba,bb=px[BENCH].get(d),px[BENCH].get(ex)
        if not(ba and bb): continue
        recs.append(100*((sum(rets)/len(rets)-cost)-(bb/ba-1.0))/H)   # %p/일 환산
    return recs

if __name__=='__main__':
    for tag,loader in [('2년 패널',load2y)]:
        px,name,dates=loader(); di={d:i for i,d in enumerate(dates)}
        print(f'=== 보유기간 스윕 · {tag} · {len(dates)}거래일 ({dates[0]}~{dates[-1]}) ===')
        print(f"{'보유H':>6s} {'n':>5s} {'전체':>9s} {'train':>9s} {'test':>9s} {'잭나이프':>9s} {'IR(일)':>9s}  판정")
        print('-'*80)
        b1=None
        for H in (1,2,3,5,7,10,15,20):
            r=run_hold(px,name,dates,di,H)
            if not r: continue
            h=len(r)//2
            f,t1,t2=statistics.mean(r),statistics.mean(r[:h]),statistics.mean(r[h:])
            if b1 is None: b1=(f,t1,t2); v='기준선(H=1)'
            else:
                ok=f>b1[0] and t1>b1[1] and t2>b1[2]
                j=jk(r)
                v=('기각(3분할 미통과)' if not ok else ('통과+잭나이프' if j>b1[0] else '가드통과·잭나이프미달'))
            j=jk(r)
            s=statistics.stdev(r)
            print(f'{H:6d} {len(r):5d} {f:+9.4f} {t1:+9.4f} {t2:+9.4f} {j:+9.4f} {statistics.mean(r)/s:+9.4f}  {v}')
        # 비용 민감도 — 알파가 비용에 얼마나 먹히는지
        print(f'\n[비용 분해] H별 총초과(비용전) vs 일당비용')
        print(f"{'H':>4s} {'비용전 %p/일':>13s} {'일당비용 %p':>12s} {'비용후 %p/일':>13s}")
        for H in (1,2,3,5,10,20):
            r0=run_hold(px,name,dates,di,H,cost=0.0)
            if not r0: continue
            print(f'{H:4d} {statistics.mean(r0):+13.4f} {-100*0.0010/H:12.4f} {statistics.mean(r0)-100*0.0010/H:+13.4f}')
