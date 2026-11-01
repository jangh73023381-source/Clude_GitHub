#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tv_shadow.py — Rule TV(거래대금 확인 필터) shadow 트래커 (2026-08-01 신설).

출처: 사용자 업로드 문서 2종(`주식매매기법_2026.docx` 전략 E,
`최근_1년_주식매매기법_조사보고서_2026.docx` 8·13절)의 반복 주장 —
"주도주 전환의 가장 좋은 신호는 업종 ETF 강세 + 거래대금 증가가 함께 나타나는 것".

규칙: 중기 슬롯 확정 규칙(Rule MM = mom150 상위 5종, Rule H 포함) 후보 중
**당일 거래대금이 직전 20거래일 평균 이상(amtsurge >= 1.0)** 인 종목만 남기고 상위 5종.

2026-08-01 검정(600거래일 패널, 보유 20거래일, KODEX200 대비, 왕복 10bp):
  baseline mom150 +0.711%p → TV +0.923%p, t 3.07 → 3.59, 오프셋 양수 15/20 → 18/20,
  오프셋 잭나이프 하한 +0.822, 임계 1.0~1.1 고원(스파이크 아님).
  단 train 0.958 < baseline 1.030 이라 **확정 승격 요건(train·test 양쪽 초과) 미충족** →
  shadow 등록. 개선분이 하락 국면(2025-09~2026-02)에 몰린 하방완화형이다.

**shadow 전용 — 실제 추천을 바꾸지 않는다.** 매일 baseline 픽5와 TV 픽5를 나란히 기록하고
보유 20거래일 뒤 채점해 `references/tv_shadow.csv` 에 누적한다.

가격은 `backtest/panel_ohlc_2y.csv`(mid_momentum_shadow.py 가 매일 갱신)를 쓴다.
선정은 D 종가까지의 정보만 사용한다 — 룩어헤드 없음. 조회 전용(주문 기능 없음).
"""
import argparse
import csv
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from universe_filters import is_cash, is_deriv  # noqa: E402
import safe_io  # noqa: E402

PANEL = os.path.join(LOOP, 'backtest', 'panel_ohlc_2y.csv')
TRACKER = os.path.join(LOOP, 'references', 'tv_shadow.csv')

BENCH = '069500'
HOLD = 1         # 채점 지평 (2026-08-06 개편: 탈락청산 = 보유집합이 그날의 픽5)
                 # 선정 파라미터(amtsurge 임계·픽 수)는 판정 전까지 동결 유지.
                 # 주의: 2026-08-01 승격 기준선은 HOLD=20 백테스트라 이제 기준선이
                 # 아니다 — 판정 전에 탈락청산 기준으로 재백테스트할 것.
NPICK = 5
LB = 150
AMT_TH = 1.0
COST = 0.0  # 2026-08-14 사용자 지시 — 왕복비용 없음(무료 수수료·ETF 거래세 면제, 겹치는 종목은 계속 보유하고 교체분만 거래). 종전값 0.0010(왕복 10bp)

COLS = ['date', 'score_date', 'status', 'base_codes', 'tv_codes',
        'n_base', 'n_tv', 'base_ret', 'tv_ret', 'kodex_ret',
        'base_excess', 'tv_excess', 'tv_minus_base', 'note']


# ---------------------------------------------------------------- 패널
def load_panel():
    bar, nm = defaultdict(dict), {}
    with open(PANEL, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                c = float(r['close'])
                v = float(r['volume'])
            except (ValueError, KeyError):
                continue
            if c <= 0:
                continue
            bar[r['code']][r['date']] = (c, c * v)
            nm[r['code']] = r['name']
    dates = sorted({d for s in bar.values() for d in s})
    return bar, nm, dates


def eligible(bar, nm, dates, i):
    d = dates[i]
    return [c for c, v in bar.items()
            if d in v and not is_deriv(nm.get(c, '')) and not is_cash(nm.get(c, ''))]


def _rank(bar, nm, dates, i, amt_filter):
    """mom150 상위 5종. amt_filter=True 면 거래대금 >= 20일 평균 조건을 추가."""
    if i < LB or i < 20:
        return []
    d, d0, d1, d3 = dates[i], dates[i - LB], dates[i - 1], dates[i - 3]
    sc = []
    for c in eligible(bar, nm, dates, i):
        v = bar[c]
        if not all(x in v for x in (d0, d1, d3)) or not v[d0][0]:
            continue
        p, p0 = v[d][0], v[d0][0]
        if p / v[d1][0] - 1 > 0.10 or p / v[d3][0] - 1 > 0.20:      # Rule H
            continue
        if amt_filter:
            prev = [dates[k] for k in range(i - 20, i)]
            amts = [v[x][1] for x in prev if x in v]
            if len(amts) < 20:
                continue
            m = sum(amts) / len(amts)
            if m <= 0 or v[d][1] / m < AMT_TH:
                continue
        sc.append((p / p0 - 1, c))
    sc.sort(reverse=True)
    return [c for _, c in sc[:NPICK]]


# ---------------------------------------------------------------- 트래커
def read_tracker():
    if not os.path.exists(TRACKER):
        return []
    with open(TRACKER, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_tracker(rows):
    tmp = TRACKER + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in COLS})
    safe_io.safe_replace(tmp, TRACKER)


def record(D=None):
    bar, nm, dates = load_panel()
    if not dates:
        print('  [tv] 패널 없음 — 건너뜀')
        return 1
    D = D or dates[-1]
    if D not in dates:
        print(f'  [tv] {D} 패널에 없음 — 건너뜀')
        return 1
    rows = read_tracker()
    if any(r['date'] == D for r in rows):
        print(f'  [tv] {D} 이미 기록됨(멱등)')
        return 0
    i = dates.index(D)
    base = _rank(bar, nm, dates, i, False)
    tv = _rank(bar, nm, dates, i, True)
    rows.append({'date': D, 'score_date': '', 'status': 'pending',
                 'base_codes': ';'.join(base), 'tv_codes': ';'.join(tv),
                 'n_base': len(base), 'n_tv': len(tv), 'note': ''})
    rows.sort(key=lambda r: r['date'])
    write_tracker(rows)
    print(f'  [tv] {D} 기록 — base {len(base)}종 / TV {len(tv)}종')
    return 0


def _port(bar, codes, d, dn, prev_codes=None):
    """탈락청산 기준 일별 손익 (2026-08-06 개편 — mid_momentum_shadow 와 동일 계산).

    Rule TV 는 mom150 후보에 얹는 필터이므로, 기저 트랙(중기)이 탈락청산으로
    확정된 이상 같은 기준으로 재야 페어 비교가 성립한다. 비용은 회전분에만 부과.
    """
    rs = []
    for c in codes:
        v = bar.get(c) or {}
        if d in v and dn in v and v[d][0]:
            rs.append(v[dn][0] / v[d][0] - 1)
    if not rs:
        return None
    cur = set(codes)
    prev = set(prev_codes) if prev_codes is not None else set()
    turnover = len(cur - prev) + len(prev - cur)
    return sum(rs) / len(rs) - turnover * COST / len(rs)


def score():
    bar, nm, dates = load_panel()
    rows = sorted(read_tracker(), key=lambda r: r['date'])
    n = 0
    for k_i, r in enumerate(rows):
        if r['status'] == 'scored' or r['date'] not in dates:
            continue
        i = dates.index(r['date'])
        if i + HOLD >= len(dates):
            continue
        d, dn = dates[i], dates[i + HOLD]
        bv = bar.get(BENCH) or {}
        if d not in bv or dn not in bv:
            continue
        prev = rows[k_i - 1] if k_i else None
        pb = [c for c in prev['base_codes'].split(';') if c] if prev else None
        pt = [c for c in prev['tv_codes'].split(';') if c] if prev else None
        kr = bv[dn][0] / bv[d][0] - 1
        br = _port(bar, [c for c in r['base_codes'].split(';') if c], d, dn, pb)
        tr = _port(bar, [c for c in r['tv_codes'].split(';') if c], d, dn, pt)
        r.update({'score_date': dn, 'status': 'scored',
                  'kodex_ret': f'{kr*100:.4f}',
                  'base_ret': f'{br*100:.4f}' if br is not None else '',
                  'tv_ret': f'{tr*100:.4f}' if tr is not None else '',
                  'base_excess': f'{(br-kr)*100:.4f}' if br is not None else '',
                  'tv_excess': f'{(tr-kr)*100:.4f}' if tr is not None else '',
                  'tv_minus_base': (f'{(tr-br)*100:.4f}'
                                    if None not in (tr, br) else '')})
        n += 1
    if n:
        write_tracker(rows)
    print(f'  [tv] {n}건 채점 (탈락청산 기준, D→D+{HOLD}거래일)')
    return 0


def report():
    rows = [r for r in read_tracker() if r['status'] == 'scored']
    xs = [float(r['tv_minus_base']) for r in rows if r['tv_minus_base']]
    if not xs:
        print(f'  [tv] 채점 완료 0건 (기록 {len(read_tracker())}건)')
        return 0
    n = len(xs)
    m = sum(xs) / n
    jk = min((sum(xs) - x) / (n - 1) for x in xs) if n >= 3 else None
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n >= 2 else 0
    print(f'  [tv] OOS {n}건 · TV-base 평균 {m:+.4f}%p · '
          f'잭나이프 하한 {jk if jk is None else round(jk, 4)} · sd {sd:.4f}')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', nargs='?', const=True)
    ap.add_argument('--score', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    rc = 0
    if a.record:
        rc |= record(None if a.record is True else a.record)
    if a.score:
        rc |= score()
    if a.report:
        rc |= report()
    if not (a.record or a.score or a.report):
        ap.print_help()
    return rc


if __name__ == '__main__':
    sys.exit(main())
