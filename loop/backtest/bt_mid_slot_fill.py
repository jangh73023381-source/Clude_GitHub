# -*- coding: utf-8 -*-
"""2026-07-31 — 중기 슬롯이 5종 미만일 때 어떻게 할 것인가 (사용자 질문).

현행 [6-2] 중기 규칙: mom60 < -10% (60일 낙폭과대) **그리고** 3일 수익률 +3%~+14% (반등 시작).
둘 다 충족한 종목만 후보로 쓰고, 5종에 못 미치면 미달인 채로 제시한다(0종이면 관망).

사용자 제안: "5개로 채워서 추천하고 단서를 달자."

검정할 것:
  Q1. 후보 수가 5 미만인 날이 실제로 얼마나 되나. 0종은 얼마나 되나.
  Q2. **후보 수 자체가 신호인가** — 후보가 적은 날에 산 중기 포지션의 성과가 나쁜가.
      나쁘다면 억지로 5종을 채우는 것은 손실을 늘린다.
  Q3. 채운다면 어떻게 채우는 게 나은가 — 조건 완화 3안 비교.

보유 20거래일(Rule MM 검정과 동일), 벤치 KODEX200, 왕복 10bp. 종가매수·종가청산.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 쓴다.
"""
import csv
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from universe_filters import is_cash, is_deriv  # noqa: E402

PANEL = os.path.join(HERE, 'panel_full.csv')
BENCH, HOLD, COST = '069500', 20, 0.0010


def load():
    px, nm = defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        px[r['code']][r['date']] = float(r['close'])
        nm[r['code']] = r['name']
    return px, nm, sorted({d for v in px.values() for d in v})


def ret(px, c, d, e):
    a, b = px[c].get(d), px[c].get(e)
    return (b / a - 1.0) if (a and b) else None


def features(px, nm, d, di, dates):
    i = di[d]
    if i < 60:
        return []
    d3, d5, d60 = dates[i - 3], dates[i - 5], dates[i - 60]
    out = []
    for c in px:
        n = nm[c]
        if is_deriv(n) or is_cash(n) or not px[c].get(d):
            continue
        m60, r3, r5 = ret(px, c, d60, d), ret(px, c, d3, d), ret(px, c, d5, d)
        if None in (m60, r3, r5):
            continue
        out.append({'code': c, 'm60': m60, 'r3': r3, 'r5': r5})
    return out


def strict(f):
    """현행 규칙."""
    p = [x for x in f if x['m60'] < -0.10 and 0.03 < x['r3'] < 0.14]
    p.sort(key=lambda x: -(x['r3'] + x['r5']))
    return p[:5]


def fill_relax_r3(f):
    """A안 — 낙폭과대(①)는 유지하고 반등 하한(+3%)만 낮춰 5종을 채운다."""
    base = strict(f)
    if len(base) >= 5:
        return base
    have = {x['code'] for x in base}
    rest = [x for x in f if x['m60'] < -0.10 and x['code'] not in have and x['r3'] < 0.14]
    rest.sort(key=lambda x: -(x['r3'] + x['r5']))
    return base + rest[:5 - len(base)]


def fill_deepest(f):
    """B안 — 조건 무시하고 60일 낙폭이 가장 큰 순으로 5종."""
    p = sorted(f, key=lambda x: x['m60'])
    return p[:5]


def fill_best_r3(f):
    """C안 — 조건 무시하고 3일 반등이 가장 강한 순으로 5종(과열 +14%↑ 제외)."""
    p = sorted([x for x in f if x['r3'] < 0.14], key=lambda x: -x['r3'])
    return p[:5]


def perf(px, picks, d, e):
    rs = [r for c in picks if (r := ret(px, c['code'], d, e)) is not None]
    b = ret(px, BENCH, d, e)
    if not rs or b is None:
        return None
    return 100 * ((sum(rs) / len(rs) - COST) - b)


def main():
    px, nm, dates = load()
    di = {d: i for i, d in enumerate(dates)}
    rng = range(60, len(dates) - HOLD)

    cnt = defaultdict(int)
    byn = defaultdict(list)
    series = {k: [] for k in ('현행(있는 만큼)', 'A 반등하한 완화', 'B 낙폭 최대', 'C 반등 최강')}
    for i in rng:
        d, e = dates[i], dates[i + HOLD]
        f = features(px, nm, d, di, dates)
        if len(f) < 30:
            continue
        s = strict(f)
        cnt[min(len(s), 5)] += 1
        p = perf(px, s, d, e)
        if p is not None:
            byn[len(s)].append(p)
        for lab, fn in (('현행(있는 만큼)', strict), ('A 반등하한 완화', fill_relax_r3),
                        ('B 낙폭 최대', fill_deepest), ('C 반등 최강', fill_best_r3)):
            pk = fn(f)
            v = perf(px, pk, d, e) if pk else 0.0      # 후보 0종이면 관망 = 초과 0
            if v is not None:
                series[lab].append(v)

    tot = sum(cnt.values())
    print(f'=== Q1. 후보 수 분포 — 선정일 {tot}일 (보유 {HOLD}일, {dates[60]}~{dates[len(dates)-HOLD-1]}) ===')
    for k in range(6):
        c = cnt.get(k, 0)
        print(f'  후보 {k}{"종 이상" if k == 5 else "종      "} : {c:4d}일 ({c / tot:5.1%})')
    short = sum(c for k, c in cnt.items() if k < 5)
    print(f'  → 5종 미만인 날 {short}일 ({short / tot:.1%}) · 0종인 날 {cnt.get(0, 0)}일 ({cnt.get(0, 0) / tot:.1%})')

    print(f'\n=== Q2. 후보 수가 신호인가 — 후보 수별 이후 {HOLD}일 초과수익 ===')
    print(f'  {"후보 수":>8s}{"일수":>6s}{"평균 초과":>11s}{"승률":>8s}')
    for k in sorted(byn):
        v = byn[k]
        if len(v) < 5:
            continue
        print(f'  {k:>8d}{len(v):6d}{statistics.fmean(v):+11.3f}{sum(1 for z in v if z > 0) / len(v):8.1%}')
    lo = [z for k, v in byn.items() if k <= 2 for z in v]
    hi = [z for k, v in byn.items() if k >= 4 for z in v]
    if lo and hi:
        print(f'  후보 0~2종인 날({len(lo)}일) 평균 {statistics.fmean(lo):+.3f}'
              f'  vs  4~5종인 날({len(hi)}일) 평균 {statistics.fmean(hi):+.3f}')

    print(f'\n=== Q3. 채우기 3안 비교 — 전 기간 평균 초과수익(%p / {HOLD}일) ===')
    base = series['현행(있는 만큼)']
    print(f'  {"방식":22s}{"평균":>9s}{"승률":>8s}{"잭나이프하한":>13s}')
    for lab, v in series.items():
        if not v:
            continue
        jk = min(statistics.fmean(v[:i] + v[i + 1:]) for i in range(len(v)))
        print(f'  {lab:22s}{statistics.fmean(v):+9.3f}{sum(1 for z in v if z > 0) / len(v):8.1%}{jk:+13.3f}')
    print(f'\n  표본 {len(base)}일 · 현행 대비 개선폭:')
    for lab, v in series.items():
        if lab != '현행(있는 만큼)':
            print(f'    {lab:22s}{statistics.fmean(v) - statistics.fmean(base):+.3f}%p')


if __name__ == '__main__':
    main()
