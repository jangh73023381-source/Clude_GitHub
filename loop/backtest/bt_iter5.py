# -*- coding: utf-8 -*-
"""2026-07-28 루프 iteration 5 — Rule PC (픽 수 확대에 의한 특이위험 희석).

기존 Rule W1/W2/W3(비중 배분 축, 2026-07-26 기각)과 구별: 비중을 바꾸는 것이 아니라
'몇 종을 담는가'(N)를 바꾼다. N 대장에 픽 수(count) 축은 아직 없다.

가설: 5종 동일가중은 mom20 상위가 한 클러스터(7/27 기준 은행·고배당)로 쏠릴 때
사실상 1개 베팅이 된다. N을 늘리면 클러스터 밖 종목이 자연히 섞여 특이위험이 희석된다.

주의: 목표 지표 중 '상위10% 5종 전부 적중'(이진)은 정의상 5종 기준이므로, 이진 지표는
동일 비교가 불가능하다. 따라서 1차지표(P&L 초과수익)로만 판정한다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bt_ruleXC import (  # noqa: E402
    load, rank_candidates, day_excess, avg, PANEL,
)


def make_pc(n):
    def sel(px, name, d, dates, _n=5):
        return rank_candidates(px, name, d, dates)[:n]
    return sel


def track_pnl(px, name, dates, fn, start=20):
    ex = []
    for i in range(start, len(dates) - 1):
        d, dn = dates[i], dates[i + 1]
        e = day_excess(px, fn(px, name, d, dates), d, dn)
        if e is not None:
            ex.append((d, e))
    return ex


def main():
    px, name, dates = load()
    print(f'패널 {os.path.basename(PANEL)} · 거래일 {len(dates)}\n')
    res = {}
    for n in (5, 7, 10, 15):
        ex = track_pnl(px, name, dates, make_pc(n))
        half = len(ex) // 2
        res[n] = {
            'full': avg([v for _, v in ex]),
            'train': avg([v for _, v in ex[:half]]),
            'test': avg([v for _, v in ex[half:]]),
            'win': sum(1 for _, v in ex if v > 0), 'n': len(ex),
        }
        r = res[n]
        lbl = 'baseline N=5' if n == 5 else f'[it5] Rule PC N={n}'
        print('%-22s [P&L] 평균 %+.3f%%p | train %+.3f%%p test %+.3f%%p | 이김 %d/%d'
              % (lbl, r['full'], r['train'], r['test'], r['win'], r['n']))

    b = res[5]
    print('\n=== 과최적화 가드 ===')
    ok_any = []
    for n in (7, 10, 15):
        r = res[n]
        m = lambda k: '▲' if r[k] > b[k] else '▼'  # noqa: E731
        ok = all(r[k] > b[k] for k in ('full', 'train', 'test'))
        if ok:
            ok_any.append(n)
        print('Rule PC N=%-3d full %s train %s test %s | %s'
              % (n, m('full'), m('train'), m('test'), '통과' if ok else '미통과'))
    print('\n가드 통과:', ok_any or '없음 — 기각, 확정방법(N=5) 유지')


if __name__ == '__main__':
    main()
