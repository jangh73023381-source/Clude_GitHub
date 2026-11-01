# -*- coding: utf-8 -*-
"""견고성 검증 — (1) RSI 밴드 파라미터 고원(plateau) 스윕, (2) 현금효과 vs 선정효과 분해,
(3) 3분할(3-fold) 안정성.

핵심 질문: T1 'RSI14 70~85 중 mom20 상위'의 초과수익이 종목을 잘 골라서인가,
아니면 후보가 적은 날 현금을 들고 있어서(마켓타이밍)인가?
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bbrsi_engine import build_cache
from bt_bbrsi import (eligible, rule_h_ok, run, summarize, show, NPICK, WARM)
from fib_engine import date_clustered_t


def mk_band(lo, hi, fill=True):
    """mom20 상위 중 RSI14가 [lo,hi]인 종목 우선 선정.
    fill=True면 부족분을 RSI 무관 차순위 mom20으로 채워 항상 5종(=순수 선정효과).
    fill=False면 부족분을 현금으로 둔다(=현금효과 포함)."""
    def f(cache, name, d, univ):
        sc = []
        for code, i in univ:
            e = cache[code]
            m = e['mom20'][i]
            if m is None or not rule_h_ok(e, i):
                continue
            r = e['rsi14'][i]
            ok = (r is not None and lo <= r <= hi)
            sc.append((m, code, ok))
        sc.sort(reverse=True)
        picks = [c for _, c, ok in sc if ok][:NPICK]
        if fill and len(picks) < NPICK:
            for _, c, ok in sc:
                if c not in picks:
                    picks.append(c)
                if len(picks) == NPICK:
                    break
        return picks
    return f


def fold3(daily):
    ex = [p - b for _, p, b, n, h in daily]
    k = len(ex) // 3
    out = []
    for a, b in ((0, k), (k, 2 * k), (2 * k, len(ex))):
        m, t, nd = date_clustered_t(ex[a:b])
        out.append(m * 100)
    return out


def main():
    cache, name, dates = build_cache()
    base_lbl, base_daily = run(cache, name, dates, mk_band(0, 101), 'BASE mom20+RuleH')
    base = summarize(base_lbl, base_daily)
    bf = fold3(base_daily)
    print(f'기준선 3분할: {bf[0]:+.4f} / {bf[1]:+.4f} / {bf[2]:+.4f} (%/일)')

    print('\n\n########## (1) RSI 밴드 파라미터 고원 스윕 — 항상 5종(선정효과만) ##########')
    rows = [base]
    for lo in (0, 40, 45, 50, 55, 60, 65, 70):
        for hi in (80, 85, 90, 95, 101):
            if lo == 0 and hi == 101:
                continue
            lbl, dly = run(cache, name, dates, mk_band(lo, hi), f'RSI {lo}~{hi} fill')
            r = summarize(lbl, dly)
            r['f3'] = fold3(dly)
            rows.append(r)
    show(rows)
    print('\n3분할 평균초과(%/일) — 기준선 대비 전부 우위인 조합만 ★')
    for r in rows[1:]:
        f3 = r['f3']
        star = '★' if all(f3[i] > bf[i] for i in range(3)) else ' '
        print(f'{star} {r["label"]:<22}{f3[0]:>9.4f}{f3[1]:>9.4f}{f3[2]:>9.4f}')

    print('\n\n########## (2) 현금효과 vs 선정효과 분해 ##########')
    rows2 = [base]
    for lo, hi in ((70, 85), (70, 101), (60, 90), (50, 101)):
        for fill in (True, False):
            tag = '항상5종(선정)' if fill else '부족시현금(선정+타이밍)'
            lbl, dly = run(cache, name, dates, mk_band(lo, hi, fill),
                           f'RSI {lo}~{hi} {tag}')
            r = summarize(lbl, dly); r['f3'] = fold3(dly)
            rows2.append(r)
    show(rows2)
    print('\n3분할:')
    for r in rows2[1:]:
        f3 = r['f3']
        print(f'  {r["label"]:<34}{f3[0]:>9.4f}{f3[1]:>9.4f}{f3[2]:>9.4f}')


if __name__ == '__main__':
    main()
