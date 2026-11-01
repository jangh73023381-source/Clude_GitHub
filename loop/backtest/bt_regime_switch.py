# -*- coding: utf-8 -*-
"""검토1 — 상승 국면에서 선정축을 바꿔야 하는가.

사용자 문제제기: "상승장이면 그에 맞는 종목선정이 되어야 하는데 지금은 방어주 위주다."
mom20 은 '최근 20일 많이 오른 것'을 고르므로, 급락 직후에는 **덜 빠진 방어형**이 상위에 온다.
V자 반등에서는 가장 많이 빠진 종목이 가장 크게 튀므로 축이 반대다.

검정: 장전에 확정되는 국면 신호로 선정축을 전환했을 때 KODEX200 대비 초과수익이 개선되는가.
국면 신호는 D 종가까지의 정보만 쓴다(룩어헤드 없음).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import doc_engine as E  # noqa: E402

COST = 0.0010
WARM = 160


# ---------------- 국면 신호 (D 종가까지) ----------------
def regimes(cache, dates):
    """지수(KODEX200) 기준 국면 플래그. i 는 D 인덱스."""
    be = cache[E.BENCH]
    px = be['px']
    n = len(px)
    dd = [None] * n          # 60일 고점 대비 낙폭
    r1 = [None] * n          # 당일 등락률
    for i in range(n):
        if i >= 60:
            h = max(px[i - 60:i + 1])
            dd[i] = px[i] / h - 1.0
        if i >= 1:
            r1[i] = px[i] / px[i - 1] - 1.0
    return {'idx': be['idx'], 'dd': dd, 'r1': r1, 'px': px}


def flag_rebound(rg, i, dd_th=-0.10, r1_th=0.02):
    """리바운드 국면: 60일 고점 대비 dd_th 이상 빠진 상태에서 당일 r1_th 이상 급등."""
    d, r = rg['dd'][i], rg['r1'][i]
    return d is not None and r is not None and d <= dd_th and r >= r1_th


def flag_drawdown(rg, i, dd_th=-0.10):
    """낙폭 국면(반등 여부 무관)."""
    d = rg['dd'][i]
    return d is not None and d <= dd_th


# ---------------- 선정축 ----------------
def pick_mom20(cache, univ):
    sc = []
    for c, i in univ:
        e = cache[c]
        m = e['mom20'][i]
        if m is not None and E.rule_h_ok(e, i):
            sc.append((m, c))
    return E.topn(sc)


def pick_reversal(cache, univ):
    """낙폭과대 — mom20 하위 5종(가장 많이 빠진 것)."""
    sc = []
    for c, i in univ:
        m = cache[c]['mom20'][i]
        if m is not None:
            sc.append((-m, c))
    return E.topn(sc)


def pick_drawdown(cache, univ):
    """60일 고점 대비 낙폭이 가장 큰 5종."""
    sc = []
    for c, i in univ:
        e = cache[c]
        if i < 60:
            continue
        h = max(e['px'][i - 60:i + 1])
        sc.append((-(e['px'][i] / h - 1.0), c))
    return E.topn(sc)


def pick_beta(cache, univ, rg):
    """고베타 — 최근 60일 지수 대비 변동성 배수 상위 5종."""
    bp = rg['px']
    sc = []
    for c, i in univ:
        e = cache[c]
        if i < 60:
            continue
        bi = rg['idx'].get(e['dates'][i])
        if bi is None or bi < 60:
            continue
        rs = [e['px'][j] / e['px'][j - 1] - 1 for j in range(i - 59, i + 1)]
        bs = [bp[j] / bp[j - 1] - 1 for j in range(bi - 59, bi + 1)]
        mb = sum(bs) / len(bs)
        vb = sum((x - mb) ** 2 for x in bs)
        if vb <= 0:
            continue
        mr = sum(rs) / len(rs)
        cov = sum((rs[k] - mr) * (bs[k] - mb) for k in range(len(rs)))
        sc.append((cov / vb, c))
    return E.topn(sc)


def pick_mom150(cache, univ):
    sc = []
    for c, i in univ:
        m = cache[c]['mom150'][i]
        if m is not None:
            sc.append((m, c))
    return E.topn(sc)


AXES = {'mom20': lambda ca, u, rg: pick_mom20(ca, u),
        '낙폭과대(mom20 하위)': lambda ca, u, rg: pick_reversal(ca, u),
        '60일 고점대비 낙폭': lambda ca, u, rg: pick_drawdown(ca, u),
        '고베타': lambda ca, u, rg: pick_beta(ca, u, rg),
        'mom150': lambda ca, u, rg: pick_mom150(ca, u)}


def run(cache, name, dates, axis_on, flag, rg, axis_off="mom20"):
    """flag 발동일엔 axis_on, 아니면 axis_off. 발동일/비발동일 성과를 분리 반환."""
    be = cache[E.BENCH]
    on, off = [], []
    for k in range(WARM, len(dates) - 1):
        d, dn = dates[k], dates[k + 1]
        bi, bj = be['idx'].get(d), be['idx'].get(dn)
        if bi is None or bj is None:
            continue
        bench = be['px'][bj] / be['px'][bi] - 1.0
        fired = flag(rg, bi)
        univ = E.eligible(cache, name, d)
        picks = AXES[axis_on if fired else axis_off](cache, univ, rg)
        rets = []
        for c in picks:
            e = cache[c]
            i, j = e['idx'][d], e['idx'].get(dn)
            if j is not None:
                rets.append(e['px'][j] / e['px'][i] - 1.0)
        if not rets:
            continue
        x = sum(rets) / len(rets) - COST - bench
        (on if fired else off).append((d, x))
    return on, off


def st(v):
    if len(v) < 3:
        return None
    n = len(v)
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))
    jk = min((sum(v) - x) / (n - 1) for x in v)
    return (m * 100, m / (sd / math.sqrt(n)) if sd else 0,
            sum(1 for x in v if x > 0) / n * 100, jk * 100, n)


def main():
    cache, name, dates = E.build()
    rg = regimes(cache, dates)

    for lbl, flag in [('리바운드(60일 -10% 낙폭 & 당일 +2%↑)', flag_rebound),
                      ('낙폭 국면(60일 고점 대비 -10%↓)', flag_drawdown)]:
        print(f'\n■ 국면: {lbl}')
        base_on, base_off = run(cache, name, dates, 'mom20', flag, rg)
        b = st([x for _, x in base_on])
        if b is None:
            print('  발동일 부족 — 검정 불가')
            continue
        print(f'  발동 {len(base_on)}일 / 비발동 {len(base_off)}일')
        o = st([x for _, x in base_off])
        print(f'  mom20 유지: 발동일 {b[0]:+.4f}%p/일 (t {b[1]:+.2f}, 승률 {b[2]:.1f}%) '
              f'| 비발동일 {o[0]:+.4f}%p/일')
        print(f'  {"전환 축":<22}{"발동일 평균%":>12}{"t":>7}{"승률%":>7}'
              f'{"잭나이프%":>11}{"vs mom20":>10}')
        print('  ' + '-' * 70)
        for ax in AXES:
            if ax == 'mom20':
                continue
            on, _ = run(cache, name, dates, ax, flag, rg)
            s = st([x for _, x in on])
            if s is None:
                continue
            print(f'  {ax:<22}{s[0]:>12.4f}{s[1]:>7.2f}{s[2]:>7.1f}'
                  f'{s[3]:>11.4f}{s[0]-b[0]:>10.4f}')

    # 최근 급락 국면(2026-07) 개별 확인
    print('\n■ 2026-07 급락·반등 구간 일자별 (mom20 vs 낙폭과대, %p/일)')
    on, off = run(cache, name, dates, '낙폭과대(mom20 하위)', flag_rebound, rg)
    b_on, _ = run(cache, name, dates, 'mom20', flag_rebound, rg)
    bd = dict(b_on)
    for d, x in on:
        if d >= '20260701':
            print(f'  {d}  mom20 {bd.get(d, float("nan")):+.3f}   낙폭과대 {x:+.3f}')


if __name__ == '__main__':
    main()
