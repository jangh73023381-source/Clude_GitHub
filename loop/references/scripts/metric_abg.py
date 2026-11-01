#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""metric_abg.py — 초과수익을 A·B·G 세 구간으로 분해한다 (조회 전용, 2026-08-22 신설).

  A  종가(D) → 종가(D+1)   = 현행 1차 지표 (v2.3/v2.8)
  G  종가(D) → 시가(D+1)   = 갭 구간 — **선정 시각 이후에 결정되는 부분**
  B  시가(D+1) → 종가(D+1) = 실제 집행 구간 (A = G + B 에 근사)

왜 필요한가 — 2026-08-21 Rule USX 사건
  USX(미국 테마 전일 수익률 가산)는 A 지표에서 baseline +0.0419 → +0.4702 로 극적으로 개선됐다.
  그런데 **개선폭 +0.428%p 중 80%(+0.339%p)가 G(갭) 구간**이었다. 미국 D 세션은 한국 종가 D
  **이후**에 열리므로, 종가 D 매수를 가정하는 A 지표로 USX 를 재면 **구조적 룩어헤드**다.
  집행 가능 구간 B 에서는 +0.0076 → +0.0956 (Δ+0.088%p) 로 5분의 1 수준이었다.
  2026-07-31 Rule US 가 "전이는 강하나 시가 이후 소멸"로 기각된 것과 같은 함정을 다른 형태로
  다시 밟은 것이다.

**1차 지표는 바꾸지 않는다.** A 를 그대로 두고 B·G 를 함께 찍는다 —
그러면 "개선분이 갭에 몰려 있는가"가 표에서 바로 보이고, 같은 함정이 자동으로 걸린다.

사용:
  python3 references/scripts/metric_abg.py --date 20260820 --picks 132030,144600,364970,228790,138530
  python3 references/scripts/metric_abg.py --date 20260820 --picks <LV> --vs <MOM>
주의: 조회 전용. 새로 조회하지 않고 `backtest/panel_ohlc_2y.csv` 만 읽는다.
"""
import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
BENCH = '069500'


def load():
    px = {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            px.setdefault(r['code'], {})[r['date']] = (float(r['open']), float(r['close']))
        except (KeyError, TypeError, ValueError):
            continue
    return px, sorted({d for v in px.values() for d in v})


def legs(px, code, d, nxt):
    """(A, G, B) — 전부 % 단위. 하나라도 없으면 None."""
    a = px.get(code, {}).get(d)
    b = px.get(code, {}).get(nxt)
    if not a or not b or not a[1] or not b[0]:
        return None
    c0, o1, c1 = a[1], b[0], b[1]
    return ((c1 / c0 - 1) * 100, (o1 / c0 - 1) * 100, (c1 / o1 - 1) * 100)


def basket(px, codes, d, nxt):
    v = [legs(px, c, d, nxt) for c in codes]
    v = [x for x in v if x]
    if len(v) != len(codes):
        return None
    return tuple(sum(x[i] for x in v) / len(v) for i in range(3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True, help='선정 기준일 D (YYYYMMDD)')
    ap.add_argument('--picks', required=True, help='쉼표 구분 코드')
    ap.add_argument('--vs', help='비교군 코드(선택) — 예: 종전 방법의 픽')
    a = ap.parse_args()

    px, dates = load()
    if a.date not in dates:
        print(f'{a.date}: 패널에 없다'); return 2
    i = dates.index(a.date)
    if i + 1 >= len(dates):
        print(f'{a.date}: 익일 종가 미확보 — 채점 불가'); return 2
    nxt = dates[i + 1]

    bm = basket(px, [BENCH], a.date, nxt)
    if not bm:
        print('벤치(069500) 결손'); return 2

    print(f'A·B·G 분해 — 선정 {a.date} → 채점 {nxt}')
    print(f'  A 종가→종가 · G 종가→시가(갭) · B 시가→종가(집행 구간)\n')
    print(f'  {"":16s}{"A":>10s}{"G(갭)":>10s}{"B(집행)":>10s}   {"A초과":>9s}{"G초과":>9s}{"B초과":>9s}')
    rows = [('픽', a.picks.split(','))]
    if a.vs:
        rows.append(('비교군', a.vs.split(',')))
    out = {}
    for lab, codes in rows:
        v = basket(px, codes, a.date, nxt)
        if not v:
            print(f'  {lab:16s} 결손 — 채점 불가'); continue
        out[lab] = v
        print(f'  {lab:16s}{v[0]:+10.3f}{v[1]:+10.3f}{v[2]:+10.3f}   '
              f'{v[0]-bm[0]:+9.3f}{v[1]-bm[1]:+9.3f}{v[2]-bm[2]:+9.3f}')
    print(f'  {"KODEX200":16s}{bm[0]:+10.3f}{bm[1]:+10.3f}{bm[2]:+10.3f}')

    if '비교군' in out:
        p, q = out['픽'], out['비교군']
        dA, dG, dB = p[0] - q[0], p[1] - q[1], p[2] - q[2]
        print(f'\n  픽 − 비교군:  A {dA:+.3f}  = G {dG:+.3f} + B {dB:+.3f}')
        if abs(dA) > 1e-9:
            share = dG / dA * 100
            print(f'  개선분 중 갭 비중 {share:.1f}%')
            if share >= 50:
                print('  ★ 경고 — 개선분의 과반이 갭 구간이다. 선정 입력이 종가 D 이후에 결정되는'
                      ' 정보를 쓰고 있지 않은지 확인할 것(Rule USX 2026-08-21 사례).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
