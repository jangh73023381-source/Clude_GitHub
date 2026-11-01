# -*- coding: utf-8 -*-
"""4~5단계 — 트랙1(피보나치 단독 선정) / 트랙2(mom20 선정 + 피보나치 집행필터) 백테스트.

채점: v2.3 손익 기준 1차 지표 — 픽 동일가중·1일 회전·왕복비용 10bp 차감 후
      KODEX200 대비 초과수익. 보조지표로 상위10% 이진 적중 병기.
룩어헤드 금지: 선정은 D종가까지, 채점은 D+1 종가.
"""
import sys, os, math
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fib_engine import (load, fib_state, is_excluded, is_cashlike, mom,
                        date_clustered_t, jackknife_low, BENCH)

MINP = 10000
NPICK = 5
COST = 0.0010          # 왕복 10bp
SPLIT = 0.5            # train/test 분할 지점


# ---------------- 후보 유니버스 ----------------
def eligible(P, i):
    ds = P['dates']; d = ds[i]; c = P['c']; nm = P['name']
    out = []
    for code in c:
        name = nm[code]
        if is_excluded(name) or is_cashlike(name):
            continue
        p = c[code].get(d)
        if not p or p < MINP:
            continue
        out.append(code)
    return out


def rule_h_ok(P, i, code):
    """v2.1 Rule H 이중 과열필터: 전일 단일세션 +10% 초과 또는 3일 누적 +20% 초과 제외."""
    ds = P['dates']; c = P['c'][code]
    if i < 3:
        return True
    p0 = c.get(ds[i]); p1 = c.get(ds[i - 1]); p3 = c.get(ds[i - 3])
    if not p0 or not p1 or not p3:
        return True
    if p0 / p1 - 1.0 > 0.10:
        return False
    if p0 / p3 - 1.0 > 0.20:
        return False
    return True


# ---------------- 선정 로직 ----------------
def pick_mom20(P, i, univ):
    sc = []
    for code in univ:
        m = mom(P, code, i, 20)
        if m is None or not rule_h_ok(P, i, code):
            continue
        sc.append((m, code))
    sc.sort(reverse=True)
    return [c for _, c in sc[:NPICK]]


def pick_fib_target(P, i, univ, L, target, regime_req='UP', trend=None):
    """되돌림이 target에 가장 가까운 종목 5종. trend=양수면 mom20>0 조건 추가."""
    sc = []
    for code in univ:
        st = fib_state(P, code, i, L)
        if st is None:
            continue
        regime, retr, chpos, H, Lo, C, amp = st
        if regime_req and regime != regime_req:
            continue
        if trend is not None:
            m = mom(P, code, i, 20)
            if m is None or m < trend:
                continue
        if not rule_h_ok(P, i, code):
            continue
        sc.append((abs(retr - target), code))
    sc.sort()
    return [c for _, c in sc[:NPICK]]


# ---------------- 채점 ----------------
def run(P, picker, label, band=None, L=None):
    """band=(lo,hi)이면 picker 결과 중 되돌림이 밴드 안인 종목만 매수(집행필터)."""
    ds = P['dates']; c = P['c']
    daily = []       # (date, port_ret_net, bench_ret, nbuy, hit)
    for i in range(120, len(ds) - 1):
        d = ds[i]; dn = ds[i + 1]
        bp = c[BENCH].get(d); bn = c[BENCH].get(dn)
        if not bp or not bn:
            continue
        bench = bn / bp - 1.0
        univ = eligible(P, i)
        picks = picker(P, i, univ)
        if band is not None:
            keep = []
            for code in picks:
                st = fib_state(P, code, i, L)
                if st is None:
                    continue
                regime, retr = st[0], st[1]
                r = retr if regime == 'UP' else None
                if r is not None and band[0] <= r <= band[1]:
                    keep.append(code)
            picks = keep
        if not picks:
            daily.append((d, 0.0, bench, 0, 0))     # 관망(현금)
            continue
        rets = []
        for code in picks:
            p = c[code].get(d); pn = c[code].get(dn)
            if p and pn:
                rets.append(pn / p - 1.0)
        if not rets:
            daily.append((d, 0.0, bench, 0, 0))
            continue
        port = sum(rets) / len(rets) - COST
        # 상위10% 적중(보조)
        u = []
        for code in univ:
            p = c[code].get(d); pn = c[code].get(dn)
            if p and pn:
                u.append((pn / p - 1.0, code))
        u.sort(reverse=True)
        cut = max(1, math.ceil(len(u) * 0.10))
        top = {code for _, code in u[:cut]}
        hit = sum(1 for code in picks if code in top)
        daily.append((d, port, bench, len(picks), hit))
    return label, daily


def summarize(label, daily, split=SPLIT):
    ex = [p - b for _, p, b, n, h in daily]
    cum_p = 1.0; cum_b = 1.0
    for _, p, b, n, h in daily:
        cum_p *= (1 + p); cum_b *= (1 + b)
    m, t, nd = date_clustered_t(ex)
    jk = jackknife_low(ex)
    k = int(len(ex) * split)
    m1, t1, _ = date_clustered_t(ex[:k])
    m2, t2, _ = date_clustered_t(ex[k:])
    nbuy = [n for _, _, _, n, _ in daily]
    hits = [h for _, _, _, n, h in daily if n > 0]
    win = sum(1 for x in ex if x > 0) / len(ex)
    return {
        'label': label, 'days': nd,
        'cum_p': (cum_p - 1) * 100, 'cum_b': (cum_b - 1) * 100,
        'mean_ex': m * 100, 't': t, 'jk': jk * 100 if jk is not None else None,
        'win': win * 100,
        'train': m1 * 100, 't_train': t1, 'test': m2 * 100, 't_test': t2,
        'avg_nbuy': sum(nbuy) / len(nbuy),
        'hit5': sum(1 for h in hits if h == 5) / len(hits) * 100 if hits else 0,
        'avg_hit': sum(hits) / len(hits) if hits else 0,
    }


def show(rows):
    print(f'\n{"전략":<34}{"일수":>5}{"누적%":>9}{"평균초과%":>10}{"t":>7}'
          f'{"잭나이프%":>10}{"승률%":>7}{"train%":>8}{"test%":>8}{"평균매수":>8}{"평균적중":>8}')
    print('-' * 122)
    for r in rows:
        print(f'{r["label"]:<34}{r["days"]:>5}{r["cum_p"]:>9.2f}{r["mean_ex"]:>10.4f}'
              f'{(r["t"] or 0):>7.2f}{(r["jk"] or 0):>10.4f}{r["win"]:>7.1f}'
              f'{r["train"]:>8.4f}{r["test"]:>8.4f}{r["avg_nbuy"]:>8.2f}{r["avg_hit"]:>8.2f}')


def main():
    P = load()
    ds = P['dates']
    print(f'기간 {ds[120]}~{ds[-1]} · 채점일 {len(ds)-121}일 · 벤치 KODEX200')
    rows = []

    # ---- baseline ----
    rows.append(summarize(*run(P, pick_mom20, 'BASE mom20+RuleH')))

    # ---- 트랙1: 피보나치 단독 선정 ----
    for L in (20, 60):
        for tgt in (0.618, 0.5, 0.382, 0.236, 0.0):
            rows.append(summarize(*run(
                P, lambda p, i, u, _L=L, _t=tgt: pick_fib_target(p, i, u, _L, _t),
                f'T1 L{L} fib{tgt} (UP)')))
        # 추세필터 결합
        for tgt in (0.618, 0.382):
            rows.append(summarize(*run(
                P, lambda p, i, u, _L=L, _t=tgt: pick_fib_target(p, i, u, _L, _t, trend=0.0),
                f'T1 L{L}fib{tgt}+mom20>0')))
    show(rows)

    # ---- 트랙2: mom20 선정 + 피보나치 집행필터 ----
    rows2 = [rows[0]]
    for L in (20, 60):
        for band in ((0.55, 0.70), (0.38, 0.70), (0.30, 0.90), (0.0, 0.30)):
            lbl = f'T2 mom20 → L{L} retr {band[0]:.2f}~{band[1]:.2f}'
            rows2.append(summarize(*run(P, pick_mom20, lbl, band=band, L=L)))
    show(rows2)


if __name__ == '__main__':
    main()
