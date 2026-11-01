# -*- coding: utf-8 -*-
"""Rule CS — 베타 정합(코어-새틀라이트 / 베타 틸트) 백테스트.

가설: 픽5의 KODEX200 대비 베타가 0.51로 구조적으로 낮다. 1차 지표가
'KODEX200 대비 초과수익'인 이상, 상승장에서 (beta-1)*E[mkt] 만큼의
기계적 드래그가 발생한다. 이를 없애는 두 계열을 검정한다.

  CS-A (대조군·코어믹스) : 픽5와 069500을 w:(1-w)로 혼합 → 순수 축소(deleveraging)
  CS-B (본후보·베타틸트) : mom20 상위 pool 안에서 베타 상위 5종 선택 → 베타를 1로 끌어올림
  CS-C (베타하한 필터)   : pool 안에서 beta >= 임계인 종목만 남기고 mom20 상위5

가드: full·train·test 3개 모두 baseline 초과 AND 잭나이프 하한 > baseline (기존 절차 동일).
룩어헤드 금지 — 베타는 D 종가까지의 수익률만 사용.
"""
import os, sys, csv, statistics
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import bt_iter2_3_20260729 as B
from bt_loop_20260806 import jackknife, tstat
B.MINP=0
BENCH='069500'
_BCACHE={}

def beta_of(px,c,d,di,dates,k=60):
    key=(c,d,k)
    if key in _BCACHE: return _BCACHE[key]
    i=di[d]
    if i<k+1: return None
    xs,ys=[],[]
    for j in range(i-k+1,i+1):
        p0,p1=px[c].get(dates[j-1]),px[c].get(dates[j])
        b0,b1=px[BENCH].get(dates[j-1]),px[BENCH].get(dates[j])
        if p0 and p1 and b0 and b1:
            ys.append(p1/p0-1.0); xs.append(b1/b0-1.0)
    if len(xs)<k*0.7: 
        _BCACHE[key]=None; return None
    mx,my=statistics.mean(xs),statistics.mean(ys)
    sxx=sum((a-mx)**2 for a in xs)
    v=(sum((a-mx)*(b-my) for a,b in zip(xs,ys))/sxx) if sxx else None
    _BCACHE[key]=v; return v

# ---- CS-B: pool 내 베타 상위 5
def cs_beta_top(cand,px=None,d=None,di=None,dates=None,pool=15,k=60,**_):
    top=sorted(cand,key=lambda x:-x['mom'])[:pool]
    sc=[(beta_of(px,x['code'],d,di,dates,k),x['code']) for x in top]
    sc=[(b,c) for b,c in sc if b is not None]
    if len(sc)<5: return B.base_sel(cand)
    sc.sort(reverse=True)
    return [c for _,c in sc[:5]]

# ---- CS-B2: mom 백분위와 베타 백분위 블렌드
def cs_blend(cand,px=None,d=None,di=None,dates=None,wgt=0.5,k=60,**_):
    rows=[]
    for x in cand:
        b=beta_of(px,x['code'],d,di,dates,k)
        if b is not None: rows.append((x['code'],x['mom'],b))
    if len(rows)<10: return B.base_sel(cand)
    ms=[m for _,m,_ in rows]; bs=[b for _,_,b in rows]
    mm,sm=statistics.mean(ms),(statistics.stdev(ms) or 1.0)
    mb,sb=statistics.mean(bs),(statistics.stdev(bs) or 1.0)
    sc=[(c,(1-wgt)*(m-mm)/sm + wgt*(b-mb)/sb) for c,m,b in rows]
    return [c for c,_ in sorted(sc,key=lambda t:-t[1])[:5]]

# ---- CS-C: 베타 하한 필터 후 mom20 상위5
def cs_floor(cand,px=None,d=None,di=None,dates=None,thr=0.8,k=60,**_):
    keep=[]
    for x in cand:
        b=beta_of(px,x['code'],d,di,dates,k)
        if b is not None and b>=thr: keep.append(x)
    if len(keep)<5: return B.base_sel(cand)
    return [x['code'] for x in sorted(keep,key=lambda x:-x['mom'])[:5]]

# ---- 대조군: 베타 하위 5 (부호 반대)
def cs_beta_bot(cand,px=None,d=None,di=None,dates=None,pool=15,k=60,**_):
    top=sorted(cand,key=lambda x:-x['mom'])[:pool]
    sc=[(beta_of(px,x['code'],d,di,dates,k),x['code']) for x in top]
    sc=[(b,c) for b,c in sc if b is not None]
    if len(sc)<5: return B.base_sel(cand)
    sc.sort()
    return [c for _,c in sc[:5]]

# ---- CS-A: 코어믹스 (run 을 따로 씀 — 가중 포트)
def run_coremix(px,name,dates,di,w,turnover_aware=True):
    recs=[]
    for i in range(21,len(dates)-1):
        d,nxt=dates[i],dates[i+1]
        cand=B.build_cand(px,name,d,di,dates)
        if len(cand)<10: continue
        picks=B.base_sel(cand)
        rets=[px[c][nxt]/px[c][d]-1.0 for c in picks if px[c].get(d) and px[c].get(nxt)]
        if not rets: continue
        ba,bb=px[BENCH].get(d),px[BENCH].get(nxt)
        if not(ba and bb): continue
        br=bb/ba-1.0
        port=(1-w)*(sum(rets)/len(rets))+w*br
        cost=B.COST*(1-w) if turnover_aware else B.COST
        recs.append(100*((port-cost)-br))
    return recs

def stats(r):
    h=len(r)//2
    return statistics.mean(r),statistics.mean(r[:h]),statistics.mean(r[h:])

def ir(r):
    s=statistics.stdev(r); return statistics.mean(r)/s if s else None

def mdd(r):
    t=0;peak=0;m=0
    for e in r:
        t+=e; peak=max(peak,t); m=min(m,t-peak)
    return m

def report(panel,label_panel):
    _BCACHE.clear()
    B.PANEL=os.path.join(HERE,panel)
    px,name,dates=B.load_panel()
    di={d:i for i,d in enumerate(dates)}
    fo,ins=B.load_flow()
    base=B.run(B.base_sel,px,name,dates,di,fo,ins)
    bf,bt_,be=stats(base)
    print(f'\n########## {label_panel} · {panel} · {len(dates)}거래일 ({dates[0]}~{dates[-1]}) ##########')
    print(f'[baseline mom20+RuleH] n={len(base)}일  full {bf:+.4f} · train {bt_:+.4f} · test {be:+.4f}'
          f'  | IR {ir(base):+.4f} · TE {statistics.stdev(base):.3f} · 초과MDD {mdd(base):+.2f}')
    print(f"\n{'변형':30s} {'전체':>9s} {'train':>9s} {'test':>9s} {'잭나이프':>9s} {'t':>6s} {'IR':>8s} {'TE':>7s} {'MDD':>8s}  판정")
    print('-'*125)
    rows=[]
    # CS-A 코어믹스
    for w in (0.2,0.4,0.6):
        r=run_coremix(px,name,dates,di,w)
        rows.append((f'CS-A 코어믹스 w{w:.1f}(대조)',r))
    variants=[
        ('CS-B 베타상위5 pool15 k60',cs_beta_top,{'pool':15,'k':60}),
        ('CS-B 베타상위5 pool20 k60',cs_beta_top,{'pool':20,'k':60}),
        ('CS-B 베타상위5 pool15 k20',cs_beta_top,{'pool':15,'k':20}),
        ('CS-B 베타상위5 pool15 k120',cs_beta_top,{'pool':15,'k':120}),
        ('CS-B2 블렌드 w0.3 k60',cs_blend,{'wgt':0.3,'k':60}),
        ('CS-B2 블렌드 w0.5 k60',cs_blend,{'wgt':0.5,'k':60}),
        ('CS-B2 블렌드 w0.7 k60',cs_blend,{'wgt':0.7,'k':60}),
        ('CS-C 베타하한 0.7 k60',cs_floor,{'thr':0.7,'k':60}),
        ('CS-C 베타하한 0.8 k60',cs_floor,{'thr':0.8,'k':60}),
        ('CS-C 베타하한 0.9 k60',cs_floor,{'thr':0.9,'k':60}),
        ('CS-D 베타하위5(대조·역방향)',cs_beta_bot,{'pool':15,'k':60}),
    ]
    for lab,fn,kw in variants:
        r=B.run(fn,px,name,dates,di,fo,ins,**kw)
        rows.append((lab,r))
    out=[]
    for lab,r in rows:
        if not r or len(r)!=len(base):
            print(f'{lab:30s} — 표본 불일치 {len(r)} vs {len(base)}'); continue
        f,t1,t2=stats(r)
        ok=f>bf and t1>bt_ and t2>be
        jk=jackknife(r) if ok else None
        tv=tstat(r,base)
        js=f'{jk:+9.4f}' if jk is not None else f'{"—":>9s}'
        ts=f'{tv:+6.2f}' if tv is not None else f'{"—":>6s}'
        if not ok: v='기각(3분할 미통과)'
        elif jk is not None and jk>bf: v='후보승격→2년재검정'; out.append(lab)
        else: v='가드통과·잭나이프미달'
        print(f'{lab:30s} {f:+9.4f} {t1:+9.4f} {t2:+9.4f} {js} {ts} {ir(r):+8.4f} {statistics.stdev(r):7.3f} {mdd(r):+8.2f}  {v}')
    return out

def load_2y_panel():
    px,name=defaultdict(dict),{}
    for r in csv.DictReader(open(os.path.join(HERE,'panel_ohlc_2y.csv'),encoding='utf-8')):
        try: px[r['code']][r['date']]=float(r['close'])
        except (ValueError,KeyError,TypeError): continue
        name[r['code']]=r['name']
    return px,name

if __name__=='__main__':
    report('panel_close_0813.csv','113일 패널')
