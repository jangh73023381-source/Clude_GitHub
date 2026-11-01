# -*- coding: utf-8 -*-
"""(b-1) 비가격축 — 거래대금·거래량 급증 2년 전수 재검증.

선행 검증: Rule AA1/AA2/AA3(거래량비율, 70일)·Rule LQ 5변형(거래대금 수준)은
이미 기각됐다. 여기서는 표본을 70일 → 459일(단기)·20오프셋(중기)로 확장하고,
'거래대금'(가격×거래량) 기준과 중기 지평을 새로 추가한다.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mid_engine import (build, run_h, stat, show, mk_rank, eligible,
                        BENCH, COST)
from fib_engine import date_clustered_t, jackknife_low

WARM = 140


def run_daily(cache, name, dates, picker, label, warm=WARM):
    be = cache[BENCH]
    ex = []; cum = 1.0
    for k in range(warm, len(dates) - 1):
        d = dates[k]; dn = dates[k + 1]
        bi = be['idx'].get(d); bj = be['idx'].get(dn)
        if bi is None or bj is None:
            continue
        bench = be['px'][bj] / be['px'][bi] - 1.0
        univ = eligible(cache, name, d)
        picks = picker(cache, name, d, univ)
        rets = []
        for c in picks:
            e = cache[c]; i = e['idx'][d]; j = e['idx'].get(dn)
            if j is not None:
                rets.append(e['px'][j] / e['px'][i] - 1.0)
        port = (sum(rets) / len(rets) - COST) if rets else 0.0
        cum *= (1 + port)
        ex.append(port - bench)
    m, t, nd = date_clustered_t(ex)
    jk = jackknife_low(ex)
    k3 = len(ex) // 3
    seg = [sum(ex[a:b]) / (b - a) * 100
           for a, b in ((0, k3), (k3, 2 * k3), (2 * k3, len(ex)))]
    return {'label': label, 'cum': (cum - 1) * 100, 'mean': m * 100, 't': t,
            'jk': jk * 100 if jk is not None else 0,
            'win': sum(1 for x in ex if x > 0) / len(ex) * 100, 'seg': seg}


def show_daily(rows):
    print(f'\n{"전략":<38}{"누적%":>10}{"평균초과%":>10}{"t":>7}{"잭나이프%":>10}'
          f'{"승률%":>7}{"1구간":>9}{"2구간":>9}{"3구간":>9}')
    print('-' * 112)
    for r in rows:
        print(f'{r["label"]:<38}{r["cum"]:>10.2f}{r["mean"]:>10.4f}{(r["t"] or 0):>7.2f}'
              f'{r["jk"]:>10.4f}{r["win"]:>7.1f}'
              f'{r["seg"][0]:>9.4f}{r["seg"][1]:>9.4f}{r["seg"][2]:>9.4f}')


STRAT = [
    (mk_rank('mom20', True), 'BASE mom20+RuleH'),
    (mk_rank('amtsurge', True), '거래대금 급증(당일/20일평균) 상위'),
    (mk_rank('amtsurge', False), '거래대금 위축 상위 (소외주)'),
    (mk_rank('amtsurge60', True), '거래대금 급증(당일/60일평균) 상위'),
    (mk_rank('volsurge', True), '거래량 급증 상위 (Rule AA 재현)'),
    (mk_rank('amt5', True), '거래대금 절대 상위 (유동성 수준)'),
    (mk_rank('amt5', False), '거래대금 절대 하위'),
    (mk_rank('amtsurge', True, cond=lambda e, i: (e['mom20'][i] or -1) > 0),
     '거래대금 급증 + mom20>0'),
    (mk_rank('amtsurge', True, cond=lambda e, i: (e['mom5'][i] or -1) > 0),
     '거래대금 급증 + mom5>0'),
    (mk_rank('mom20', True, cond=lambda e, i: (e['amtsurge'][i] or 0) > 1.5),
     'mom20 중 거래대금급증>1.5 (필터)'),
    (mk_rank('mom20', True, cond=lambda e, i: (e['amtsurge'][i] or 0) > 1.0),
     'mom20 중 거래대금급증>1.0 (필터)'),
    (mk_rank('mom20', True, cond=lambda e, i: (e['amtsurge'][i] or 9) < 1.0),
     'mom20 중 거래대금 위축 (필터)'),
    (mk_rank('mom120', True, cond=lambda e, i: (e['amtsurge'][i] or 0) > 1.0),
     'mom120 중 거래대금급증>1.0 (중기용)'),
]


def main():
    cache, name, dates = build()
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    print(f'유니버스 {len(cache)}종 · {dates[0]}~{dates[-1]}')

    if mode in ('all', 'd'):
        print('\n\n########## 단기 H=1 (익일 종가 청산, 459일) ##########')
        rows = [run_daily(cache, name, dates, p, l) for p, l in STRAT]
        show_daily(rows)
        b = rows[0]
        print('\n3분할 전 구간 기준선 초과:')
        hit = False
        for r in rows[1:]:
            if all(r['seg'][i] > b['seg'][i] for i in range(3)):
                print(f'  ★ {r["label"]}  전체 {r["mean"]:+.4f} (기준선 {b["mean"]:+.4f})')
                hit = True
        if not hit:
            print('  없음')

    if mode in ('all', 'm'):
        print('\n\n########## 중기 H=20 (겹치지 않는 20오프셋) ##########')
        rows2 = []
        for p, l in STRAT:
            _, per, allobs = run_h(cache, name, dates, p, l, H=20)
            rows2.append((l, stat(per, allobs)))
        show(rows2)


if __name__ == '__main__':
    main()
