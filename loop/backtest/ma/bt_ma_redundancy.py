# -*- coding: utf-8 -*-
"""핵심 진단 — MA 게이트는 mom20과 중복인가?

가설: 20일 모멘텀 상위 5종은 정의상 이미 MA20 위 / MA20 상승 중이다.
      그렇다면 MA 지지·저항 필터는 mom20 위에 얹을 때 발동 자체를 거의 안 하고,
      선정 레이어가 모멘텀이 아닐 때(검색·관심 기반 등) 비로소 유효해진다.

검증
  (1) mom20 top5 픽이 MA 조건을 이미 만족하는 비율
  (2) 선정 레이어를 바꿔가며(모멘텀 / 역모멘텀 / 무작위) MA 게이트의 기여도 측정
"""
import os
import sys
import random
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ma_engine import load, Panel
import bt_ma_support as B

BENCH = '069500'
COST = 0.0010


def diag_overlap(P, codes, dates):
    tot = 0
    sat = {'MA20위': 0, 'MA20기울기>0': 0, '정배열': 0, 'MA60위': 0}
    for i in range(B.WARMUP, len(dates) - 1):
        d = dates[i]
        for c in B.select(P, codes, d, None):
            tot += 1
            dz = P.disp(c, d, 20)
            sl = P.slope(c, d, 20, 5)
            al = P.aligned(c, d)
            h = P.head(c, d, 60)
            if dz is not None and dz > 0:
                sat['MA20위'] += 1
            if sl is not None and sl > 0:
                sat['MA20기울기>0'] += 1
            if al:
                sat['정배열'] += 1
            if h is not None and h < 0:
                sat['MA60위'] += 1
    print('=' * 78)
    print('(1) mom20 top5 픽이 이미 MA 조건을 만족하는 비율 (15섹터, 픽 %d건)' % tot)
    print('=' * 78)
    for k, v in sat.items():
        bar = '█' * int(v / tot * 40)
        print(f'  {k:14s} {v/tot*100:5.1f}%  {bar}')
    print('\n  → 비율이 높을수록 MA 필터는 mom20과 중복이며 발동 여지가 없다.')


def rank_by(P, codes, d, mode, rng):
    cand = []
    for c in codes:
        m = P.mom(c, d, 20)
        if m is None or not B.rule_h_ok(P, c, d):
            continue
        cand.append((c, m))
    if mode == 'mom':
        cand.sort(key=lambda x: x[1], reverse=True)
    elif mode == 'rev':
        cand.sort(key=lambda x: x[1])
    else:
        rng.shuffle(cand)
    return [c for c, _ in cand]


def run_mode(P, codes, dates, mode, gate, seed=7):
    rng = random.Random(seed)
    xs = []
    fired = 0
    for i in range(B.WARMUP, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        ranked = rank_by(P, codes, d, mode, rng)
        if gate is None:
            picks = ranked[:5]
        else:
            keep = [c for c in ranked if gate(P, c, d) is not False]
            picks = keep[:5] if len(keep) >= 5 else (keep + [c for c in ranked if c not in keep])[:5]
        if len(picks) < 5:
            continue
        if gate is not None and set(picks) != set(ranked[:5]):
            fired += 1
        a, b = P.close(BENCH, d), P.close(BENCH, dn)
        if not (a and b):
            continue
        rs = [P.close(c, dn) / P.close(c, d) - 1.0 for c in picks
              if P.close(c, d) and P.close(c, dn)]
        if len(rs) == 5:
            xs.append(sum(rs) / 5 - COST - (b / a - 1.0))
    return statistics.mean(xs) * 100 if xs else None, fired


def main():
    bars, meta, dates, codes = load()
    P = Panel(bars, dates)
    diag_overlap(P, codes, dates)

    gates = [
        ('없음(baseline)', None),
        ('MA-T MA20기울기>0', B.g_ma20_slope),
        ('MA-A 정배열', B.g_aligned),
        ('MA-R3 저항반락 배제', B.g_rejected),
        ('MA-S1 지지이탈<=1%', B.mk_g_support(0.01)),
    ]
    modes = [('모멘텀 top5 (현행)', 'mom'), ('역모멘텀 bottom5', 'rev'), ('무작위 5종', 'rnd')]

    print()
    print('=' * 78)
    print('(2) 선정 레이어별 MA 게이트 기여도 — KODEX200 대비 일평균 초과수익 %')
    print('=' * 78)
    hdr = f"{'MA 게이트':22s}" + ''.join(f'{m[0]:>20s}' for m in modes)
    print(hdr)
    print('-' * len(hdr))
    base = {}
    for label, g in gates:
        cells = []
        for mlabel, mode in modes:
            v, fired = run_mode(P, codes, dates, mode, g)
            if g is None:
                base[mode] = v
                cells.append(f'{v:>13.4f}      ')
            else:
                d = v - base[mode]
                cells.append(f'{v:>13.4f}({d:+.3f})'.rjust(20))
        print(f'{label:22s}' + ''.join(cells))
    print('\n  괄호 = baseline 대비 순증(%p). 선정이 모멘텀이 아닐수록 MA 게이트 기여가 커지면')
    print('  "MA 필터는 모멘텀과 중복, 비모멘텀 선정에서 유효" 가설이 확인된다.')


if __name__ == '__main__':
    main()
