# -*- coding: utf-8 -*-
"""bt_nullimok_20260822.py — 유튜브 '눌림목 매매 200전 200승' 규칙 검정 (60분봉 원안 그대로).

영상(주식탐구소, 2026-08-21, OKbzCdcAay0)에서 추출한 규격:
  · 차트: **60분봉**
  · 이동평균: MA240(초록) · MA480(검정)  ← 60분봉 기준. 하루 6봉이므로 ≈ 40일 · 80일
  · 보조지표: **스토캐스틱 슬로우 (8, 6, 6)**
  · 매수: ① 240선 이탈 확인 → ② 480선 아래로 내려온 구간에서
          ③ 스토캐스틱 침체(과매도) '웅덩이' + 골든크로스 확인 후 **분할 매수**
  · 매도: 스토캐스틱 **과열(과매수) 구간**에서 매도
  · 대상: 대형주·거래대금 큰 주도주 (영상 예시 = 한화오션)

검정 설계 (CLAUDE.md §4 준수)
  · 표본: 시총 상위 120종 중 60분봉 확보 116종 · 2023-08~2026-08 (약 4,300봉/종목)
  · 채점: 진입~청산 절대수익, **같은 구간 KODEX200 수익 차감 = 초과수익**
  · t 는 **일자 클러스터 보정** (텔레그램 검정 2026-08-13 교훈 — 미보정 시 t 부풀려짐)
  · **무작위 진입 대조군 필수** (Rule BX 2026-08-08 교훈 — 목표가 청산 구조 자체가 원인일 수 있음)
"""
import json, math, random, statistics, datetime
from collections import defaultdict

S=json.load(open('bars60m.json')); B=S['bars']; META=S['meta']
BENCH='069500'
bench=B[BENCH]
bt={r[0]:r[3] for r in bench}
btimes=sorted(bt)

def sma(v,n):
    out=[None]*len(v); s=0.0
    for i,x in enumerate(v):
        s+=x
        if i>=n: s-=v[i-n]
        if i>=n-1: out[i]=s/n
    return out

def stoch(h,l,c,k=8,s1=6,s2=6):
    fk=[None]*len(c)
    for i in range(len(c)):
        if i<k-1: continue
        hh=max(h[i-k+1:i+1]); ll=min(l[i-k+1:i+1])
        fk[i]=50.0 if hh<=ll else (c[i]-ll)/(hh-ll)*100
    def smooth(v,n):
        out=[None]*len(v); buf=[]
        for i,x in enumerate(v):
            if x is None: buf=[]; continue
            buf.append(x)
            if len(buf)>n: buf.pop(0)
            if len(buf)==n: out[i]=sum(buf)/n
        return out
    sk=smooth(fk,s1); sd=smooth(sk,s2)
    return sk,sd

def bench_ret(t0,t1):
    import bisect
    i=bisect.bisect_left(btimes,t0); j=bisect.bisect_left(btimes,t1)
    if i>=len(btimes) or j>=len(btimes): return None
    a,b=bt[btimes[i]],bt[btimes[j]]
    return (b/a-1)*100 if a else None

def signals(code, MA1=240, MA2=480, OS=20, OB=80, CAP=240, random_entry=False, seed=0):
    b=B[code]
    if len(b)<MA2+60: return []
    ts=[r[0] for r in b]; h=[r[1] for r in b]; l=[r[2] for r in b]; c=[r[3] for r in b]
    m1=sma(c,MA1); m2=sma(c,MA2); sk,sd=stoch(h,l,c)
    out=[]; i=MA2+20
    rnd=random.Random(hash(code)+seed)
    while i < len(c)-1:
        ok=False
        if random_entry:
            ok = rnd.random() < 0.004          # 발동 빈도를 원안과 비슷하게
        else:
            # ① 240선 이탈 이력(최근 120봉 내) ② 현재 480선 아래
            broke240 = any(c[j] is not None and m1[j] is not None and c[j]<m1[j]
                           for j in range(max(0,i-120),i+1))
            below480 = m2[i] is not None and c[i] < m2[i]
            # ③ 과매도 웅덩이(최근 20봉 내 SlowK<OS) + 골든크로스(K가 D를 상향 돌파)
            if broke240 and below480 and sk[i] is not None and sd[i] is not None and sk[i-1] is not None:
                dip = any(sk[j] is not None and sk[j]<OS for j in range(max(0,i-20),i+1))
                gx  = sk[i-1] <= sd[i-1] and sk[i] > sd[i]
                ok = dip and gx
        if ok:
            entry=c[i]; t0=ts[i]
            ex=None
            for j in range(i+1, min(i+1+CAP, len(c))):
                if sk[j] is not None and sk[j] >= OB:      # 과매수 도달 → 매도
                    ex=(c[j], ts[j], j, 'ob'); break
            if ex is None:
                j=min(i+CAP, len(c)-1); ex=(c[j], ts[j], j, 'cap')
            r=(ex[0]/entry-1)*100
            bm=bench_ret(t0, ex[1])
            if bm is not None:
                out.append(dict(code=code, t0=t0, bars=ex[2]-i, ret=r, ex=r-bm, how=ex[3]))
            i=ex[2]+1                                     # 중복 진입 방지
        else:
            i+=1
    return out

def report(trades, lab):
    if len(trades)<5:
        print(f'  {lab}: 거래 {len(trades)}건 — 표본 부족'); return None
    ex=[t['ex'] for t in trades]; rr=[t['ret'] for t in trades]
    # 일자 클러스터 보정 t
    byd=defaultdict(list)
    for t in trades:
        byd[datetime.datetime.utcfromtimestamp(t['t0']).strftime('%Y%m%d')].append(t['ex'])
    dm=[statistics.mean(v) for v in byd.values()]
    m=statistics.mean(ex)
    tcl=(statistics.mean(dm)/(statistics.stdev(dm)/len(dm)**0.5)) if len(dm)>2 else float('nan')
    ob=sum(1 for t in trades if t['how']=='ob')
    print(f'  {lab:34s} 거래{len(trades):5d} 절대{statistics.mean(rr):+7.2f}% '
          f'초과{m:+7.2f}%p (일자클러스터 t={tcl:+5.2f}) 승률{sum(1 for x in ex if x>0)/len(ex)*100:5.1f}% '
          f'중앙{statistics.median(ex):+6.2f} 보유{statistics.mean(t["bars"] for t in trades):5.1f}봉 '
          f'과매수청산{ob/len(trades)*100:4.0f}%')
    return dict(n=len(trades), ex=m, t=tcl, med=statistics.median(ex))

codes=[c for c in B if c!=BENCH]
print(f'표본 {len(codes)}종 · 60분봉 (하루 6봉) · MA240≈40일 · MA480≈80일\n')
print('=== 원안 그대로 ===')
base=[t for c in codes for t in signals(c)]
r0=report(base,'원안 (240이탈→480아래→스토 GX)')

print('\n=== 무작위 진입 대조군 (같은 청산 구조) — Rule BX 교훈 ===')
for s in range(3):
    rnd=[t for c in codes for t in signals(c, random_entry=True, seed=s)]
    report(rnd, f'무작위 진입 seed{s}')

print('\n=== 조건 분해 — 어느 조각이 값을 만드는가 ===')
for lab,kw in (('480 아래 조건만(스토 무시)',dict(OS=101)),
               ('스토 GX만(MA 조건 무시)',dict(MA1=1,MA2=1))):
    pass
def variant(name, **kw):
    tr=[t for c in codes for t in signals(c, **kw)]
    report(tr, name)
variant('MA 조건 완화 240만 (480 무시)', MA2=240)
variant('과매도 임계 30', OS=30)
variant('과매도 임계 10', OS=10)
variant('과매수 청산 70', OB=70)
variant('과매수 청산 90', OB=90)
variant('보유 캡 120봉(20일)', CAP=120)
variant('보유 캡 480봉(80일)', CAP=480)
print('\n=== 고원 — MA 조합 스윕 ===')
for a,b_ in ((120,240),(180,360),(240,480),(300,600),(360,720)):
    variant(f'MA{a}/{b_}', MA1=a, MA2=b_)

# ── 결과 요약 (2026-08-22 실행) ────────────────────────────────────────────
#  표본 115종 · 60분봉 2023-08~2026-08
#  원안: 거래 3,392 · 절대 +1.46% · 승률 55.2% · **KODEX200 대비 초과 −0.17%p (t=−0.34)**
#  무작위 진입 대조군(같은 청산): 절대 +1.03~+1.13% · 승률 54.4~54.8%  ← 원안과 사실상 동일
#  → 성과는 진입이 아니라 **청산 구조**가 만든다. Rule BX(2026-08-08)와 같은 진단.
#  과매수 청산분 98.1% 승률 66.3% / 캡 강제청산 1.9% 절대 −5.25% 승률 14.1%
#  → "200전 200승"의 정체: 이기는 거래만 닫고 지는 거래는 계속 들고 있는 구조.
#  MA 조합 5종·과매도 3종·과매수 3종·캡 3종 = **전 변형 초과 음수. 양수 변형 0개.**
#  영상 예시 한화오션(042660): 25거래 절대 +1.24% 초과 **−0.94%p** 승률 72%
