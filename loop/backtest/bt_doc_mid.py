# -*- coding: utf-8 -*-
"""중기 트랙(보유 20거래일, Rule MM mom150) — 업로드 문서 기법 검정.

평가는 mid_engine 의 겹치지 않는 다중 오프셋 방식(오프셋 0..19)을 그대로 쓴다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import doc_engine as E  # noqa: E402
from mid_engine import stat, show  # noqa: E402

H = 20
WARM = 170
COST = 0.0010


def run_h(cache, name, dates, picker, label):
    be = cache[E.BENCH]
    per, allobs = [], []
    for off in range(H):
        obs = []
        k = WARM + off
        while k + H < len(dates):
            d, dn = dates[k], dates[k + H]
            bi, bj = be['idx'].get(d), be['idx'].get(dn)
            if bi is None or bj is None:
                k += H
                continue
            bench = be['px'][bj] / be['px'][bi] - 1.0
            univ = E.eligible(cache, name, d)
            picks = picker(cache, name, d, univ)
            rets = []
            for c in picks:
                e = cache[c]
                i = e['idx'][d]
                j = e['idx'].get(dn)
                if j is not None:
                    rets.append(e['px'][j] / e['px'][i] - 1.0)
            obs.append((sum(rets) / len(rets) - COST - bench) if rets else -bench)
            k += H
        if obs:
            per.append(sum(obs) / len(obs))
            allobs += obs
    return label, per, allobs


def p_mom150(cache, name, d, univ):
    sc = []
    for c, i in univ:
        m = cache[c]['mom150'][i]
        if m is not None:
            sc.append((m, c))
    return E.topn(sc)


def _f(cond, key='mom150'):
    def picker(cache, name, d, univ):
        sc = []
        for c, i in univ:
            e = cache[c]
            v = e[key][i]
            if v is None or not cond(e, i):
                continue
            sc.append((v, c))
        return E.topn(sc)
    return picker


def c_above150(e, i):
    """문서 3절 ①추세 확인: 종가가 150일선 위."""
    m = e['ma150'][i]
    return m is not None and e['px'][i] > m


def c_stack(e, i):
    """정배열: 종가 > 20일선 > 60일선 (문서 전략 A '20/60일선 위 우상향')."""
    a, b = e['ma20'][i], e['ma60'][i]
    return None not in (a, b) and e['px'][i] > a > b


def c_pullback(e, i):
    """문서 전략 B 눌림목: 20일선 ±3% 근접 + 조정 시 거래량 감소."""
    a, vs = e['ma20'][i], e['volsurge'][i]
    if None in (a, vs) or not a:
        return False
    return -0.03 <= e['px'][i] / a - 1.0 <= 0.03 and vs < 1.0


def c_flow20(e, i):
    """문서 전략 C 수급 추세: 외국인 20일 누적 순매수 > 0."""
    f = e['for20'][i]
    return f is not None and f > 0


def c_flow_both20(e, i):
    f, o = e['for20'][i], e['org20'][i]
    return None not in (f, o) and f > 0 and o > 0


def c_amt(e, i):
    """문서 전략 E: 거래대금 유입(20일 평균 대비 증가)."""
    a = e['amtsurge'][i]
    return a is not None and a >= 1.0


def c_ruleh(e, i):
    return E.rule_h_ok(e, i)


def c_notover(e, i):
    """문서 실전팁: 돌파 당일 급등이 과도하면 추격 회피(채널 최상단 제외)."""
    cp = e['chpos60'][i]
    return cp is not None and cp < 0.98


def c_chan_hi(e, i):
    """채널 상단권(0.80~0.95) — 기존 백테스트에서 최강 구간으로 확인된 영역."""
    cp = e['chpos60'][i]
    return cp is not None and 0.80 <= cp <= 0.95


def main():
    cache, name, dates = E.build()
    print(f'패널 {len(dates)}거래일 {dates[0]}~{dates[-1]}, H={H}')
    tests = [
        ('M0 기준선 mom150 상위5', p_mom150),
        ('M1 +150일선 위', _f(c_above150)),
        ('M2 +정배열(20>60)', _f(c_stack)),
        ('M3 +20일선 눌림목', _f(c_pullback)),
        ('M4 +외국인20일 순매수', _f(c_flow20)),
        ('M5 +외국인·기관 동반20일', _f(c_flow_both20)),
        ('M6 +거래대금 증가', _f(c_amt)),
        ('M7 +Rule H 과열필터', _f(c_ruleh)),
        ('M8 +과열추격 회피(ch<0.98)', _f(c_notover)),
        ('M9 +채널상단 0.80~0.95', _f(c_chan_hi)),
        ('M10 +150선위 & 정배열',
         _f(lambda e, i: c_above150(e, i) and c_stack(e, i))),
        ('M11 +150선위 & 수급',
         _f(lambda e, i: c_above150(e, i) and c_flow20(e, i))),
    ]
    rows = []
    for lbl, f in tests:
        l, per, allobs = run_h(cache, name, dates, f, lbl)
        rows.append((l, stat(per, allobs)))
    show(rows)


if __name__ == '__main__':
    main()
