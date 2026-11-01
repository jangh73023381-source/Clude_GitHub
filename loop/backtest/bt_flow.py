# -*- coding: utf-8 -*-
"""(b-2) 비가격축 — 외국인·기관 순매수(수급) 백테스트, 2년 전수.

데이터: 키움 ka10045 기관·외국인 일별 순매매 수량 (backtest/flow_2y.csv, 600거래일).
순매매 '수량'이므로 종목 간 비교를 위해 반드시 정규화한다:
  net_rate   = 순매수수량 / 당일 거래량            (거래 대비 매수 강도)
  net_amt    = 순매수수량 × 종가                   (금액 환산)
  net_ratio5 = 5일 누적 순매수수량 / 5일 누적 거래량  (지속성)
  streak     = 연속 순매수 일수
단기 H=1과 중기 H=20 양쪽에서 검증한다.
"""
import sys, os, csv
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mid_engine import (build, run_h, stat, show, mk_rank, eligible,
                        rule_h_ok, BENCH, COST, NPICK)
from fib_engine import date_clustered_t, jackknife_low

HERE = os.path.dirname(os.path.abspath(__file__))
FLOW = os.path.join(HERE, 'flow_2y.csv')
WARM = 140


def attach_flow(cache):
    """flow_2y.csv를 가격 캐시의 날짜 인덱스에 정렬해 붙인다."""
    raw = defaultdict(dict)
    with open(FLOW, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                raw[r['code']][r['date']] = (
                    float(r['volume']), float(r['orgn_net']), float(r['for_net']))
            except Exception:
                continue
    miss = 0
    for code, e in cache.items():
        n = len(e['px'])
        for key in ('orgn_rate', 'for_rate', 'both_rate', 'orgn_r5', 'for_r5',
                    'both_r5', 'orgn_streak', 'for_streak', 'both_amt'):
            e[key] = [None] * n
        src = raw.get(code)
        if not src:
            miss += 1
            continue
        on = [None] * n; fn = [None] * n; vl = [None] * n
        for i, d in enumerate(e['dates']):
            v = src.get(d)
            if v:
                vl[i], on[i], fn[i] = v
        for i in range(n):
            if vl[i] and vl[i] > 0:
                if on[i] is not None:
                    e['orgn_rate'][i] = on[i] / vl[i]
                if fn[i] is not None:
                    e['for_rate'][i] = fn[i] / vl[i]
                if on[i] is not None and fn[i] is not None:
                    e['both_rate'][i] = (on[i] + fn[i]) / vl[i]
                    e['both_amt'][i] = (on[i] + fn[i]) * e['px'][i]
            if i >= 5:
                sv = sum(x for x in vl[i - 4:i + 1] if x)
                so = sum(x for x in on[i - 4:i + 1] if x is not None)
                sf = sum(x for x in fn[i - 4:i + 1] if x is not None)
                if sv > 0:
                    e['orgn_r5'][i] = so / sv
                    e['for_r5'][i] = sf / sv
                    e['both_r5'][i] = (so + sf) / sv
            # 연속 순매수 일수
            for key, arr in (('orgn_streak', on), ('for_streak', fn)):
                s = 0
                j = i
                while j >= 0 and arr[j] is not None and arr[j] > 0:
                    s += 1; j -= 1
                e[key][i] = s
            so_ = e['orgn_streak'][i]; sf_ = e['for_streak'][i]
            e['both_streak'] = e.get('both_streak') or [None] * n
            e['both_streak'][i] = min(so_ or 0, sf_ or 0)
    print(f'수급 데이터 미보유 종목 {miss}종')
    return cache


def run_daily(cache, name, dates, picker, label, warm=WARM):
    be = cache[BENCH]
    ex = []; cum = 1.0; nb = []
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
        cum *= (1 + port); nb.append(len(picks))
        ex.append(port - bench)
    m, t, nd = date_clustered_t(ex)
    jk = jackknife_low(ex)
    k3 = len(ex) // 3
    seg = [sum(ex[a:b]) / (b - a) * 100
           for a, b in ((0, k3), (k3, 2 * k3), (2 * k3, len(ex)))]
    return {'label': label, 'cum': (cum - 1) * 100, 'mean': m * 100, 't': t,
            'jk': jk * 100 if jk is not None else 0,
            'win': sum(1 for x in ex if x > 0) / len(ex) * 100, 'seg': seg,
            'nb': sum(nb) / len(nb)}


def show_daily(rows):
    print(f'\n{"전략":<38}{"누적%":>10}{"평균초과%":>10}{"t":>7}{"잭나이프%":>10}'
          f'{"승률%":>7}{"1구간":>9}{"2구간":>9}{"3구간":>9}{"매수":>6}')
    print('-' * 118)
    for r in rows:
        print(f'{r["label"]:<38}{r["cum"]:>10.2f}{r["mean"]:>10.4f}{(r["t"] or 0):>7.2f}'
              f'{r["jk"]:>10.4f}{r["win"]:>7.1f}{r["seg"][0]:>9.4f}{r["seg"][1]:>9.4f}'
              f'{r["seg"][2]:>9.4f}{r["nb"]:>6.2f}')


def main():
    cache, name, dates = build()
    attach_flow(cache)
    mode = sys.argv[1] if len(sys.argv) > 1 else 'd'

    strat = [
        (mk_rank('mom20', True), 'BASE mom20+RuleH'),
        (mk_rank('both_rate', True), '외국인+기관 순매수강도(당일) 상위'),
        (mk_rank('orgn_rate', True), '기관 순매수강도(당일) 상위'),
        (mk_rank('for_rate', True), '외국인 순매수강도(당일) 상위'),
        (mk_rank('both_rate', False), '외국인+기관 순매도강도 상위 (역발상)'),
        (mk_rank('both_r5', True), '외국인+기관 5일누적 순매수비율 상위'),
        (mk_rank('orgn_r5', True), '기관 5일누적 순매수비율 상위'),
        (mk_rank('for_r5', True), '외국인 5일누적 순매수비율 상위'),
        (mk_rank('both_amt', True), '외국인+기관 순매수 금액 상위'),
        (mk_rank('orgn_streak', True), '기관 연속 순매수일수 상위'),
        (mk_rank('for_streak', True), '외국인 연속 순매수일수 상위'),
        (mk_rank('mom20', True, cond=lambda e, i: (e['both_rate'][i] or -9) > 0),
         'mom20 중 외국인+기관 순매수 (필터)'),
        (mk_rank('mom20', True, cond=lambda e, i: (e['both_r5'][i] or -9) > 0),
         'mom20 중 5일누적 순매수 (필터)'),
        (mk_rank('both_r5', True, cond=lambda e, i: (e['mom20'][i] or -1) > 0),
         '5일누적 순매수 상위 + mom20>0'),
        (mk_rank('mom120', True, cond=lambda e, i: (e['both_r5'][i] or -9) > 0),
         'mom120 중 5일누적 순매수 (중기용)'),
    ]

    if mode in ('d', 'all'):
        print('\n\n########## 단기 H=1 (익일 종가 청산) ##########')
        rows = [run_daily(cache, name, dates, p, l) for p, l in strat]
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

    if mode in ('m', 'all'):
        print('\n\n########## 중기 H=20 (겹치지 않는 20오프셋) ##########')
        rows2 = []
        for p, l in strat:
            _, per, allobs = run_h(cache, name, dates, p, l, H=20)
            rows2.append((l, stat(per, allobs)))
        show(rows2)


if __name__ == '__main__':
    main()
