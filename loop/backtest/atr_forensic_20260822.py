# -*- coding: utf-8 -*-
"""ATR 결함 포렌식 — 자격증명 없이, 이미 있는 산출물만으로 원인을 좁힌다.

브리핑 산출물 `_sector_levels_YYYYMMDD.json` 10개(8/03~8/14)는 전부 KRX 공식 패널
(`krx_stock_panel.csv`, 20260303~20260814) 범위 안에 있다.
→ 같은 날 같은 종목에 대해 **키움 산출값 vs KRX 공식 재계산**을 항목별로 150쌍 대조할 수 있다.

핵심 감별:
  · **20/60일 고점·저점이 맞는가** = 키움의 고가/저가 극값이 정확한가
  · **MA20/MA60이 맞는가** = 키움의 종가 계열이 정확한가
  · **ATR14만 틀린가** = 그렇다면 문제는 피드가 아니라 ATR 계산 경로/윈도우다
"""
import csv, json, glob, os, re, statistics
from collections import defaultdict

K=defaultdict(dict)
for r in csv.DictReader(open('/mnt/user-data/uploads/loop/backtest/krx_stock_panel.csv',encoding='utf-8-sig')):
    try: K[r['code']][r['date']]=(float(r['open']),float(r['high']),float(r['low']),float(r['close']))
    except (TypeError,ValueError): pass
DATES=sorted({d for v in K.values() for d in v})

def bars(code, upto):
    ds=[d for d in sorted(K[code]) if d<=upto]
    return [(d,)+K[code][d] for d in ds]

def atr14(b):
    if len(b)<15: return None
    return sum(max(b[i][2]-b[i][3], abs(b[i][2]-b[i-1][4]), abs(b[i][3]-b[i-1][4]))
               for i in range(len(b)-14,len(b)))/14
def ma(b,n): return sum(x[4] for x in b[-n:])/n if len(b)>=n else None
def hi(b,n): return max(x[2] for x in b[-n:]) if len(b)>=n else None
def lo(b,n): return min(x[3] for x in b[-n:]) if len(b)>=n else None

rows=[]
for f in sorted(glob.glob('/mnt/user-data/uploads/fable/_sector_levels_*.json')):
    fd=re.search(r'(\d{8})',f).group(1)
    prev=[d for d in DATES if d<fd]
    if not prev: continue
    D=prev[-1]                       # 장전 생성 → 전 거래일 종가 기준
    for r in json.load(open(f,encoding='utf-8')):
        c=r.get('code')
        if r.get('error') or c not in K or D not in K[c]: continue
        b=bars(c,D)
        if len(b)<65: continue
        if abs(r['close']-K[c][D][3])>1:     # 기준일 불일치면 건너뜀
            continue
        rows.append(dict(f=fd,D=D,code=c,name=r['name'],
            kw_atr=r['atr'], krx_atr=atr14(b),
            kw=r, krx=dict(ma20=ma(b,20),ma60=ma(b,60),h20=hi(b,20),l20=lo(b,20),
                           h60=hi(b,60),l60=lo(b,60),close=K[c][D][3])))
print(f'대조 쌍 {len(rows)}개 · 날짜 {len(set(r["f"] for r in rows))}개 · 종목 {len(set(r["code"] for r in rows))}개\n')

# ── 1) 레벨 라벨별 일치율 ─────────────────────────────────────────
match=defaultdict(lambda:[0,0])
for r in rows:
    for k in ('s1','s2','r1','r2'):
        it=r['kw'].get(k)
        if not it: continue
        lab=it['label']; px=it['price']
        for nm,key in (('MA20','ma20'),('MA60','ma60'),('20일고점','h20'),('20일저점','l20'),
                       ('60일고점','h60'),('60일저점','l60')):
            if nm in lab and r['krx'][key]:
                ok = abs(px/r['krx'][key]-1) < 0.002
                match[nm][0]+=ok; match[nm][1]+=1
print('=== 레벨 항목별 일치율 (키움 산출 vs KRX 공식 재계산, 허용 0.2%) ===')
for nm,(o,n) in sorted(match.items(), key=lambda x:-x[1][1]):
    print(f'  {nm:8s} {o:4d}/{n:4d} = {o/n*100:5.1f}%')

# ── 2) 종가 일치 ────────────────────────────────────────────────
cm=sum(1 for r in rows if abs(r['kw']['close']-r['krx']['close'])<1)
print(f'\n  종가      {cm:4d}/{len(rows):4d} = {cm/len(rows)*100:5.1f}%')

# ── 3) ATR 비율 ────────────────────────────────────────────────
rt=[r['krx_atr']/r['kw_atr'] for r in rows if r['kw_atr'] and r['krx_atr']]
print(f'\n=== ATR14 — KRX재계산 / 키움 ===')
print(f'  n={len(rt)} · 평균 {statistics.mean(rt):.4f} · 중앙 {statistics.median(rt):.4f} '
      f'· sd {statistics.pstdev(rt):.4f} · 최소 {min(rt):.3f} · 최대 {max(rt):.3f}')
print(f'  1.00 근처(±1%) 비율 {sum(1 for x in rt if abs(x-1)<0.01)/len(rt)*100:.1f}%')

# ── 4) 종목별·날짜별 비율 안정성 ────────────────────────────────
print('\n=== 종목별 ATR 비율 (10일 평균) — 종목 고유값인가, 날짜 효과인가 ===')
byc=defaultdict(list); byd=defaultdict(list)
for r in rows:
    if r['kw_atr'] and r['krx_atr']:
        byc[r['name']].append(r['krx_atr']/r['kw_atr']); byd[r['f']].append(r['krx_atr']/r['kw_atr'])
for n,v in sorted(byc.items(), key=lambda x:-statistics.mean(x[1])):
    print(f'  {n[:14]:15s} 평균 {statistics.mean(v):.3f} (sd {statistics.pstdev(v):.3f}, n={len(v)})')
print('\n=== 날짜별 ATR 비율 ===')
for d,v in sorted(byd.items()):
    print(f'  {d} 평균 {statistics.mean(v):.3f} (sd {statistics.pstdev(v):.3f}, n={len(v)})')
