#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cd_shadow.py — Rule CD(캔들 꼬리 신호) shadow 트래커 (2026-07-31 신설).

규칙: mom20 상위 15종 풀에서 **캔들점수(윗꼬리비율 - 아래꼬리비율) 상위 5종**을 뽑는다.
2026-07-31 검정(603거래일)에서 baseline(mom20+RuleH) 대비 full +0.0337 vs -0.0266,
3분할 3/3 우위, 잭나이프 하한 +0.0509 로 전 가드를 통과했다.

**사용자 가설과 방향이 반대다.** 아래꼬리가 긴 망치형이 오르는 게 아니라 **내렸고**
(IC -0.0387, t -4.55), 윗꼬리가 긴 유성형이 올랐다(+0.0239, t +2.99).

**shadow 전용 — 실제 추천을 바꾸지 않는다.** 매일 baseline 픽5와 CD 픽5를 나란히 채점해
`references/cd_shadow.csv` 에 누적하고, `judge_ready.py` 의 N* 기준으로 승격을 판정한다.

가격은 `backtest/panel_ohlc_2y.csv`(mid_momentum_shadow.py 가 매일 갱신)를 쓴다.
선정은 D-1 종가까지의 정보만 사용한다 — 룩어헤드 없음. 조회 전용.
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from universe_filters import is_cash, is_deriv  # noqa: E402

PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
OUT = os.path.join(LOOP, 'references', 'cd_shadow.csv')
COLS = ['date', 'sel_date', 'base_codes', 'cd_codes', 'base_ret', 'cd_ret',
        'bench_ret', 'base_excess', 'cd_excess', 'cd_minus_base', 'note']
BENCH, POOL = '069500', 15      # 동결 파라미터 — 판정 전까지 변경 금지
COST = 0.0  # 2026-11-01: v2.8(2026-08-14) 무비용 전환 때 누락됐던 곳 — CLAUDE.md §5 "채점 비용"대로 0으로 정정(이 스크립트는 종결된 Rule CD이지만 morning_run.py가 지금도 매일 호출한다)


def load():
    bar, nm = defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            o, h, l, c = (float(r['open']), float(r['high']),
                          float(r['low']), float(r['close']))
        except (ValueError, KeyError):
            continue
        if min(o, h, l, c) <= 0 or h < l:
            continue
        nm[r['code']] = r['name']
        bar[r['code']][r['date']] = (o, h, l, c)
    bar = {c: v for c, v in bar.items() if not is_deriv(nm[c]) and not is_cash(nm[c])}
    return bar, nm, sorted({d for v in bar.values() for d in v})


def picks(bar, dates, di, d):
    """D 종가 기준 baseline5 · CD5 를 만든다."""
    i = di[d]
    if i < 21:
        return [], []
    cs = []
    for c, v in bar.items():
        if d not in v:
            continue
        need = [dates[i - k] for k in (1, 3, 20)]
        if not all(x in v for x in need):
            continue
        r1 = v[d][3] / v[dates[i - 1]][3] - 1
        r3 = v[d][3] / v[dates[i - 3]][3] - 1
        if r1 > 0.10 or r3 > 0.20:              # Rule H
            continue
        o, h, l, cl = v[d]
        rng = h - l
        if rng <= 0:
            continue
        body = abs(cl - o)
        score = ((h - max(o, cl)) - (min(o, cl) - l)) / rng
        cs.append({'code': c, 'mom': v[d][3] / v[dates[i - 20]][3] - 1,
                   'score': score, 'body': body})
    if len(cs) < 20:
        return [], []
    top = sorted(cs, key=lambda x: -x['mom'])
    base = [x['code'] for x in top[:5]]
    cd = [x['code'] for x in sorted(top[:POOL], key=lambda x: -x['score'])[:5]]
    return base, cd


def rows():
    return list(csv.DictReader(open(OUT, encoding='utf-8'))) if os.path.exists(OUT) else []


def record(D):
    if D in {r['date'] for r in rows()}:
        print(f'  [cd_shadow] {D} 이미 기록됨 — 생략(멱등)')
        return 0
    bar, nm, dates = load()
    if D not in dates:
        print(f'  [cd_shadow] {D} 패널에 없음 — 기록 보류')
        return 1
    di = {d: i for i, d in enumerate(dates)}
    i = di[D]
    if i == 0:
        return 1
    sel = dates[i - 1]
    base, cd = picks(bar, dates, di, sel)
    if not base or not cd:
        print(f'  [cd_shadow] {sel} 선정 불가 — 기록 보류')
        return 1

    def pr(codes):
        rs = [bar[c][D][3] / bar[c][sel][3] - 1 for c in codes
              if bar[c].get(sel) and bar[c].get(D)]
        return 100 * (sum(rs) / len(rs)) - COST if rs else None
    b, cdr = pr(base), pr(cd)
    bench = bar[BENCH][D][3] / bar[BENCH][sel][3] - 1 if bar[BENCH].get(sel) else None
    if b is None or cdr is None or bench is None:
        print(f'  [cd_shadow] {D} 가격 결손 — 기록 보류')
        return 1
    bench = 100 * bench
    new = not os.path.exists(OUT)
    with open(OUT, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow({'date': D, 'sel_date': sel, 'base_codes': '|'.join(base),
                    'cd_codes': '|'.join(cd), 'base_ret': round(b, 3),
                    'cd_ret': round(cdr, 3), 'bench_ret': round(bench, 3),
                    'base_excess': round(b - bench, 3), 'cd_excess': round(cdr - bench, 3),
                    'cd_minus_base': round(cdr - b, 3),
                    'note': f'OOS 실기록 pool={POOL}'})
    same = len(set(base) & set(cd))
    print(f'  [cd_shadow] {D} 기록 — CD {cdr:+.2f}% vs baseline {b:+.2f}% '
          f'(차이 {cdr - b:+.2f}%p) · 픽 중복 {same}/5')
    return 0


def report():
    rr = rows()
    if not rr:
        print('  [cd_shadow] 기록 없음')
        return
    d = [float(r['cd_minus_base']) for r in rr]
    m = sum(d) / len(d)
    win = sum(1 for x in d if x > 0)
    print(f'  [cd_shadow] 누적 {len(rr)}일 · CD-baseline 평균 {m:+.3f}%p · 이김 {win}/{len(rr)}')
    print('    승격 판정: python3 references/scripts/judge_ready.py '
          'references/cd_shadow.csv cd_minus_base')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', metavar='D')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    rc = record(a.record) if a.record else 0
    if a.report or not a.record:
        report()
    sys.exit(rc)
