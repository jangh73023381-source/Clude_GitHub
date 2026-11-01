# -*- coding: utf-8 -*-
"""트랙 A(단기 ETF, 보유 1일) — 업로드 문서 기법 검정.

기준선: v1.9 mom20 상위 5종 + v2.1 Rule H (현행 확정 방법).
지표  : KODEX200 대비 1일 초과수익(왕복 10bp 차감), 평균/t/승률/train·test/잭나이프.
"""
import math
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from doc_engine import build, eligible, rule_h_ok, topn, BENCH, COST  # noqa: E402

WARM = 160   # ma150 까지 필요


def run(cache, name, dates, picker, label):
    be = cache[BENCH]
    obs = []
    for k in range(WARM, len(dates) - 1):
        d, dn = dates[k], dates[k + 1]
        bi, bj = be['idx'].get(d), be['idx'].get(dn)
        if bi is None or bj is None:
            continue
        bench = be['px'][bj] / be['px'][bi] - 1.0
        univ = eligible(cache, name, d)
        picks = picker(cache, name, d, univ)
        rets = []
        for c in picks:
            e = cache[c]
            i = e['idx'][d]
            j = e['idx'].get(dn)
            if j is not None:
                rets.append(e['px'][j] / e['px'][i] - 1.0)
        if rets:
            obs.append((d, sum(rets) / len(rets) - COST - bench, len(picks)))
    return label, obs


def stat(obs):
    v = [x[1] for x in obs]
    n = len(v)
    if n < 3:
        return None
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))
    t = m / (sd / math.sqrt(n)) if sd > 0 else 0.0
    win = sum(1 for x in v if x > 0) / n * 100
    half = n // 2
    tr = sum(v[:half]) / half
    te = sum(v[half:]) / (n - half)
    # 잭나이프(1일 제거) 하한
    tot = sum(v)
    jk = min((tot - x) / (n - 1) for x in v)
    trade = sum(1 for x in obs if x[2] > 0)
    return dict(mean=m * 100, t=t, win=win, n=n, train=tr * 100, test=te * 100,
                jk=jk * 100, trade=trade)


def show(rows):
    print(f'{"전략":<30}{"평균초과%":>10}{"t":>7}{"승률%":>7}{"train%":>9}'
          f'{"test%":>9}{"잭나이프%":>11}{"일수":>6}')
    print('-' * 92)
    for lbl, s in rows:
        if s is None:
            print(f'{lbl:<30}  (관측 부족)')
            continue
        print(f'{lbl:<30}{s["mean"]:>10.4f}{s["t"]:>7.2f}{s["win"]:>7.1f}'
              f'{s["train"]:>9.4f}{s["test"]:>9.4f}{s["jk"]:>11.4f}{s["n"]:>6}')


# ---------------- 선정 규칙 ----------------

def p_base(cache, name, d, univ):
    """기준선: mom20 상위 5종 + Rule H."""
    sc = []
    for c, i in univ:
        e = cache[c]
        m = e['mom20'][i]
        if m is None or not rule_h_ok(e, i):
            continue
        sc.append((m, c))
    return topn(sc)


def _filtered(cache, univ, cond, key='mom20', n=5):
    sc = []
    for c, i in univ:
        e = cache[c]
        v = e[key][i]
        if v is None or not rule_h_ok(e, i):
            continue
        if not cond(e, i):
            continue
        sc.append((v, c))
    return topn(sc, n)


def _pullback(e, i, band=0.03):
    """문서 ①-② 20일선 눌림목: 상승추세 + 20일선 근접 + 조정 시 거래량 감소."""
    ma5, ma20 = e['ma5'][i], e['ma20'][i]
    vs = e['volsurge'][i]
    if None in (ma5, ma20, vs) or not ma20:
        return False
    if ma5 <= ma20:                       # 단기 추세 살아있음
        return False
    dist = e['px'][i] / ma20 - 1.0
    return (-band <= dist <= band) and vs < 1.0


def _above_ma5(e, i):
    """문서 ①-① 5이평선 타기: 종가가 5일선 위 + 5일선 > 20일선."""
    ma5, ma20 = e['ma5'][i], e['ma20'][i]
    return None not in (ma5, ma20) and e['px'][i] > ma5 > ma20


def _breakout(e, i, k=20, vmin=1.5):
    """문서 전략 A 거래량 동반 돌파: 직전 N일 최고 종가 상향 + 거래량 증가 + 20일선 위."""
    ph, ma20, vs = e[f'prevhi{k}'][i], e['ma20'][i], e['volsurge'][i]
    if None in (ph, ma20, vs):
        return False
    return e['px'][i] > ph and vs >= vmin and e['px'][i] > ma20


def _gapup(e, i, g=0.01):
    """문서 ② 시초가 갭상승 + 시가 지지(종가 >= 시가)."""
    gp = e['gap'][i]
    return gp is not None and gp >= g and e['bull'][i]


def _flow(e, i, days=5):
    """문서 전략 C 수급 추세: 외국인 N일 누적 순매수 > 0 이면서 가격 상승."""
    f = e[f'for{days}'][i]
    m = e['mom5'][i]
    return f is not None and f > 0 and m is not None and m > 0


def _flow_both(e, i):
    f, o = e['for5'][i], e['org5'][i]
    return f is not None and o is not None and f > 0 and o > 0


def _oversold(e, i):
    """문서 ⑤ 역발상: RSI 과매도 + 양봉 전환 + 거래량 증가."""
    r, vs = e['rsi14'][i], e['volsurge'][i]
    if None in (r, vs):
        return False
    return r < 35 and e['bull'][i] and vs > 1.2


def _box_break(e, i):
    """문서 ④ 박스권 상단 돌파: 60일 채널 최상단권 + 거래대금 증가."""
    cp, a = e['chpos60'][i], e['amtsurge'][i]
    return None not in (cp, a) and cp >= 0.98 and a >= 1.2


def _triple(cache, name, d, univ):
    """문서 13절 3중 필터 점수제(ETF 적용: 수급·차트 2축, 각 0~2)."""
    sc = []
    for c, i in univ:
        e = cache[c]
        if not rule_h_ok(e, i):
            continue
        s = 0
        f5, o5 = e['for5'][i], e['org5'][i]
        if f5 is not None and f5 > 0:
            s += 1
        if o5 is not None and o5 > 0:
            s += 1
        ma20, ma60 = e['ma20'][i], e['ma60'][i]
        if None not in (ma20, ma60) and e['px'][i] > ma20 > ma60:
            s += 1
        a = e['amtsurge'][i]
        if a is not None and a >= 1.2:
            s += 1
        m = e['mom20'][i]
        if m is None or s < 3:
            continue
        sc.append((s + min(m, 0.99), c))     # 점수 우선, 동점은 mom20
    return topn(sc)


def main():
    cache, name, dates = build()
    print(f'패널 {len(dates)}거래일 {dates[0]}~{dates[-1]}, 종목 {len(cache)}')
    rows = []
    rows.append(run(cache, name, dates, p_base, 'A0 기준선 mom20+RuleH'))
    tests = [
        ('A1 20일선 눌림목(±3%)', lambda c, n, d, u: _filtered(c, u, _pullback)),
        ('A2 20일선 눌림목(±5%)',
         lambda c, n, d, u: _filtered(c, u, lambda e, i: _pullback(e, i, 0.05))),
        ('A3 5이평선 타기', lambda c, n, d, u: _filtered(c, u, _above_ma5)),
        ('A4 거래량돌파 20일(1.5x)', lambda c, n, d, u: _filtered(c, u, _breakout)),
        ('A5 거래량돌파 20일(2.0x)',
         lambda c, n, d, u: _filtered(c, u, lambda e, i: _breakout(e, i, 20, 2.0))),
        ('A6 거래량돌파 60일(1.5x)',
         lambda c, n, d, u: _filtered(c, u, lambda e, i: _breakout(e, i, 60, 1.5))),
        ('A7 갭상승+시가지지(1%)', lambda c, n, d, u: _filtered(c, u, _gapup)),
        ('A8 갭상승+시가지지(2%)',
         lambda c, n, d, u: _filtered(c, u, lambda e, i: _gapup(e, i, 0.02))),
        ('A9 외국인5일 순매수', lambda c, n, d, u: _filtered(c, u, _flow)),
        ('A10 외국인+기관 동반', lambda c, n, d, u: _filtered(c, u, _flow_both)),
        ('A11 RSI 역발상', lambda c, n, d, u: _filtered(c, u, _oversold)),
        ('A12 박스권 상단돌파', lambda c, n, d, u: _filtered(c, u, _box_break)),
        ('A13 3중필터 점수>=3', _triple),
    ]
    for lbl, f in tests:
        rows.append(run(cache, name, dates, f, lbl))
    show([(l, stat(o)) for l, o in rows])

    # 매매일 수(픽이 0종이 아닌 날) 확인
    print('\n[픽 산출일 수]')
    for l, o in rows:
        nz = sum(1 for x in o if x[2] > 0)
        avg = sum(x[2] for x in o) / len(o) if o else 0
        print(f'  {l:<30} 픽생성일 {nz:>4}/{len(o)}  평균 {avg:.2f}종')


if __name__ == '__main__':
    main()
