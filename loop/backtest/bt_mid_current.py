# -*- coding: utf-8 -*-
"""현행 [6-2] 중기 ETF 선정룰(낙폭과대 반등)을 mom120과 직접 대조.

현행 룰(morning_run.py): mom60 < -10% 인 후보 중 최근 3일+5일 수익률 합 상위.
'낙폭과대 + 단기반등'은 평균회귀 축이므로, 20일 보유 지평에서 실제로 어떤지 확인한다.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mid_engine import (build, run_h, stat, show, mk_rank, rule_h_ok, NPICK)


def add(cache, lb):
    key = f'mom{lb}'
    for code, e in cache.items():
        if key in e:
            continue
        px = e['px']; a = [None] * len(px)
        for i in range(lb, len(px)):
            if px[i - lb]:
                a[i] = px[i] / px[i - lb] - 1.0
        e[key] = a


def pick_current(cache, name, d, univ):
    """현행 중기룰 재현: mom60 < -0.10, r3 과열(+14%↑) 제외, r3+r5 상위 5종."""
    sc = []
    for code, i in univ:
        e = cache[code]
        m60 = e['mom60'][i]
        if m60 is None or m60 >= -0.10 or i < 6:
            continue
        px = e['px']
        r3 = px[i] / px[i - 3] - 1.0
        r5 = px[i] / px[i - 5] - 1.0
        if r3 > 0.14:
            continue
        sc.append((r3 + r5, code))
    sc.sort(reverse=True)
    return [c for _, c in sc[:NPICK]]


def pick_current_nofloor(cache, name, d, univ):
    """낙폭 조건만 (반등 조건 없이) — 어느 쪽이 문제인지 분리."""
    sc = []
    for code, i in univ:
        e = cache[code]
        m60 = e['mom60'][i]
        if m60 is None or m60 >= -0.10:
            continue
        sc.append((m60, code))
    sc.sort()
    return [c for _, c in sc[:NPICK]]


def main():
    cache, name, dates = build()
    for lb in (120, 150):
        add(cache, lb)
    print(f'{len(cache)}종 · {dates[0]}~{dates[-1]}')
    strat = [
        (mk_rank('mom20', True), 'BASE mom20 (단기룰을 중기에 적용)'),
        (pick_current, '현행 [6-2] 중기룰 (낙폭과대 + 3·5일 반등)'),
        (pick_current_nofloor, '낙폭과대만 (반등조건 제거)'),
        (mk_rank('mom120', True), 'mom120 상위 (신규 후보)'),
        (mk_rank('mom150', True), 'mom150 상위 (신규 후보)'),
    ]
    for H in (10, 20, 40):
        print(f'\n########## 보유 {H}일 ##########')
        rows = []
        for p, l in strat:
            _, per, allobs = run_h(cache, name, dates, p, l, H=H, warm=160)
            rows.append((l, stat(per, allobs)))
        show(rows)


if __name__ == '__main__':
    main()
