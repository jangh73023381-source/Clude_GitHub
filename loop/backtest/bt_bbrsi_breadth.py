# -*- coding: utf-8 -*-
"""(3) 사후가설 검증 — 'RSI 후보 수'를 시장 브레드스 관망신호로 쓰면?

RSI 70~85 전략의 초과수익이 전부 현금 보유에서 나온다는 분해 결과에서 파생된
사후(post-hoc) 가설이다. 다중검정 경고를 붙여 별도 검정한다.

룰: 당일 RSI14가 [lo,hi]인 적격 ETF 수(breadth)가 임계 미만이면 전량 관망,
    아니면 평소대로 mom20+RuleH 상위 5종 매수.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bbrsi_engine import build_cache
from bt_bbrsi import eligible, rule_h_ok, run, summarize, show, NPICK
from bt_bbrsi_robust import fold3
from fib_engine import date_clustered_t, jackknife_low


def mk_breadth(thr, lo=70, hi=85):
    def f(cache, name, d, univ):
        n = 0; sc = []
        for code, i in univ:
            e = cache[code]
            if not rule_h_ok(e, i):
                continue
            r = e['rsi14'][i]
            if r is not None and lo <= r <= hi:
                n += 1
            m = e['mom20'][i]
            if m is not None:
                sc.append((m, code))
        if n < thr:
            return []
        sc.sort(reverse=True)
        return [c for _, c in sc[:NPICK]]
    return f


def main():
    cache, name, dates = build_cache()
    base_lbl, base_daily = run(cache, name, dates, mk_breadth(0), 'BASE mom20+RuleH')
    base = summarize(base_lbl, base_daily); base['f3'] = fold3(base_daily)
    rows = [base]
    for thr in (1, 2, 3, 5, 8, 12, 20):
        lbl, dly = run(cache, name, dates, mk_breadth(thr),
                       f'브레드스(RSI70~85 개수)>={thr}일 때만 매수')
        r = summarize(lbl, dly); r['f3'] = fold3(dly)
        rows.append(r)
    show(rows)
    bf = base['f3']
    print(f'\n3분할 (기준선 {bf[0]:+.4f}/{bf[1]:+.4f}/{bf[2]:+.4f}) — 전 구간 우위만 ★')
    for r in rows[1:]:
        f3 = r['f3']
        star = '★' if all(f3[i] > bf[i] for i in range(3)) else ' '
        print(f'{star} {r["label"]:<34}{f3[0]:>9.4f}{f3[1]:>9.4f}{f3[2]:>9.4f}')


if __name__ == '__main__':
    main()
