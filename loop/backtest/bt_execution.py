# -*- coding: utf-8 -*-
"""2026-07-31 — 집행 방법 비교: 갭 때문에 지정가가 안 걸리면 어떻게 할 것인가.

사용자 질문: "장 시작하면 갭상승·갭하락이라 단기 종목 매매가 어려울 것 같다."

브리핑은 '전일종가 ×1.006 이하 지정가'를 매수상단으로 제시한다. 실제로
  · 그 지정가가 얼마나 자주 체결되는가(체결률)
  · 체결 안 된 날을 놓치는 게 이득인가 손해인가
  · 아예 시초가에 사는 것과 비교하면 어느 쪽이 나은가
를 600거래일 패널로 잰다.

집행안
  A 종가매수(이론)   : 전일 종가에 산다. 실제로는 불가능 — 저장소 표준 채점 관행의 기준선.
  B 시초가 매수      : 갭을 그대로 받아들이고 09:00 시가에 산다.
  C 지정가(상단+0.6%): 시가<=상단이면 시가 체결, 아니면 장중 저가<=상단일 때만 상단에 체결.
  D 지정가 미체결시 시초가 대체 : C 로 안 걸린 종목만 시가로 산다.
전부 당일 종가 청산, 왕복 10bp, 벤치 KODEX200 대비 초과수익(%p/일).
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

PANEL = os.path.join(HERE, 'panel_ohlc_2y.csv')
BENCH, COST, LIMIT = '069500', 0.0010, 1.006


def load():
    bar, nm = defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            o, h, l, c = (float(r['open']), float(r['high']),
                          float(r['low']), float(r['close']))
        except (ValueError, KeyError):
            continue
        if min(o, h, l, c) <= 0:
            continue
        nm[r['code']] = r['name']
        bar[r['code']][r['date']] = (o, h, l, c)
    bar = {c: v for c, v in bar.items() if not is_deriv(nm[c]) and not is_cash(nm[c])}
    return bar, nm, sorted({d for v in bar.values() for d in v})


def mom(bar, c, d, di, dates, k):
    i = di[d]
    if i < k:
        return None
    a, b = bar[c].get(dates[i - k]), bar[c].get(d)
    return (b[3] / a[3] - 1.0) if (a and b) else None


def picks5(bar, nm, d, di, dates):
    cs = []
    for c, v in bar.items():
        if d not in v:
            continue
        m = mom(bar, c, d, di, dates, 20)
        r1 = mom(bar, c, d, di, dates, 1)
        r3 = mom(bar, c, d, di, dates, 3)
        if m is None or r1 is None or r3 is None:
            continue
        if r1 > 0.10 or r3 > 0.20:
            continue
        cs.append((m, c))
    cs.sort(reverse=True)
    return [c for _, c in cs[:5]]


def main():
    bar, nm, dates = load()
    di = {d: i for i, d in enumerate(dates)}
    res = {k: [] for k in 'ABCD'}
    gaps, fills, miss_ret, fill_ret = [], [], [], []

    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        p = picks5(bar, nm, d, di, dates)
        if len(p) < 5 or nxt not in bar[BENCH] or d not in bar[BENCH]:
            continue
        bo, bc = bar[BENCH][nxt][0], bar[BENCH][nxt][3]
        b_cc = bc / bar[BENCH][d][3] - 1
        b_oc = bc / bo - 1
        ra, rb, rc, rd, nfill = [], [], [], [], 0
        for c in p:
            if d not in bar[c] or nxt not in bar[c]:
                continue
            pc = bar[c][d][3]
            o, h, l, cl = bar[c][nxt]
            lim = pc * LIMIT
            gaps.append(o / pc - 1)
            ra.append(cl / pc - 1)
            rb.append(cl / o - 1)
            if o <= lim:                       # 갭이 상단 이하 → 시가 체결
                rc.append(cl / o - 1)
                rd.append(cl / o - 1)
                nfill += 1
                fills.append(1)
                fill_ret.append(cl / pc - 1)
            elif l <= lim:                     # 장중에 눌러줘야 체결
                rc.append(cl / lim - 1)
                rd.append(cl / lim - 1)
                nfill += 1
                fills.append(1)
                fill_ret.append(cl / pc - 1)
            else:                              # 미체결
                fills.append(0)
                miss_ret.append(cl / pc - 1)
                rd.append(cl / o - 1)          # D안: 시가로 대체 매수
        if not ra:
            continue
        res['A'].append(100 * ((sum(ra) / len(ra) - COST) - b_cc))
        res['B'].append(100 * ((sum(rb) / len(rb) - COST) - b_oc))
        res['C'].append(100 * (((sum(rc) / len(rc) - COST) - b_oc) if rc else 0.0))
        res['D'].append(100 * ((sum(rd) / len(rd) - COST) - b_oc))

    n = len(res['A'])
    print(f'표본 {n}일 ({dates[21]}~{dates[-2]}) · 픽5 동일가중 · 왕복 10bp · 벤치 대비 %p/일\n')
    print(f'  체결률 {statistics.fmean(fills):.1%} '
          f'(픽·날 조합 {len(fills)}건 중 체결 {sum(fills)}건)')
    g = sorted(gaps)
    print(f'  갭(시가/전일종가-1) 중앙값 {statistics.median(g):+.2f}% · '
          f'상위10% {g[int(len(g) * .9)] * 100:+.1f}% · 하위10% {g[int(len(g) * .1)] * 100:+.1f}%')
    up = sum(1 for x in gaps if x > 0.006)
    print(f'  갭이 매수상단(+0.6%)을 넘은 비율 {up / len(gaps):.1%}\n')
    print(f'  {"집행안":28s}{"평균 초과":>10s}{"승률":>8s}')
    print('  ' + '-' * 46)
    for k, lab in (('A', 'A 전일종가 매수(이론·불가)'), ('B', 'B 시초가 매수'),
                   ('C', 'C 지정가만(미체결=현금)'), ('D', 'D 지정가+미체결은 시가')):
        v = res[k]
        print(f'  {lab:28s}{statistics.fmean(v):+10.4f}{sum(1 for x in v if x > 0) / len(v):8.1%}')
    print(f'\n  체결된 픽의 당일 수익률 평균 {statistics.fmean(fill_ret) * 100:+.3f}%')
    print(f'  미체결(갭업으로 놓친) 픽의 당일 수익률 평균 {statistics.fmean(miss_ret) * 100:+.3f}%'
          f'  ← 놓친 게 이득인지 손해인지')


if __name__ == '__main__':
    main()
