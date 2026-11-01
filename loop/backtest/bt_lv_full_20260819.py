#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_lv_full_20260819.py — Rule LV(저변동 틸트) 정식 검정, 7년 패널 · 보강 지표 기준.

배경 — 사용자 승인 (2026-08-19)
  "지표 보강 + LOWVOL 정식 검정". 현행 1차 지표(일평균 %p 초과)로는 LV−MOM = -0.0086%p
  (t=-0.27)로 무차별인데, 복리 누적·MDD·Sharpe 로는 명백히 우월했다. 사용자는 픽5를 매일
  전액 매수하므로 체감 지표는 복리와 MDD 다. 지표를 보강하고 이 규칙을 6관문으로 검정한다.

규칙 LV: mom20 상위 pool 종 후보 중 **최근 k일 실현변동성 하위 5종**을 고른다.
  · 유니버스·Rule H·비용(0) 전부 현행 그대로. 바뀌는 것은 상위 pool 내 정렬 기준뿐이다.
  · 입력은 ETF 종가뿐이라 **선정 시각에 100% 확보 가능**(실전 조달 검정 통과).

6관문(CLAUDE.md §4-4·4-5·4-6)
  R1 파라미터 고원(축마다) · R2 3분할·6분할 fold · R3 정의 교체 · R4 플라시보 순열 ·
  R5 꼬리 기여도 · 실전 조달.
  ※ R4 가 특히 중요하다 — **저변동 5종은 서로 상관이 낮아 '분산효과만으로' MDD 가 내려갈 수
    있다.** 무작위 5종 귀무분포와 비교해야 변동성 선택 자체의 값을 분리할 수 있다.
"""
import os, random, statistics, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_base_long_20260819 as L


def cum(rs):
    x, o = 1.0, []
    for r in rs:
        x *= (1 + r / 100)
        o.append(x)
    return o


def mdd(cv):
    pk, w = cv[0], 0.0
    for x in cv:
        pk = max(pk, x)
        w = min(w, x / pk - 1)
    return w * 100


def prof(v, label=''):
    c = cum(v)
    n = len(v)
    yrs = n / 252
    sd = statistics.stdev(v)
    return {'label': label, 'n': n, 'cum': (c[-1] - 1) * 100,
            'cagr': (c[-1] ** (1 / yrs) - 1) * 100, 'mdd': mdd(c),
            'sharpe': statistics.mean(v) / sd * 252 ** 0.5, 'sd': sd,
            'mean': statistics.mean(v), 'curve': c}


def show(p, b=None):
    d = '' if b is None else (f'  ΔCAGR{p["cagr"]-b["cagr"]:+6.1f}%p '
                              f'ΔMDD{p["mdd"]-b["mdd"]:+6.1f}%p ΔSharpe{p["sharpe"]-b["sharpe"]:+5.2f}')
    print(f'  {p["label"]:30s} 누적{p["cum"]:+8.1f}% CAGR{p["cagr"]:+6.1f}% '
          f'MDD{p["mdd"]:7.1f}% Sharpe{p["sharpe"]:5.2f} sd{p["sd"]:5.2f}{d}')


def main():
    px, names = L.load()
    dates = sorted({d for c in px for d in px[c]})
    cands = L.build(px, names, dates)
    pos = {d: i for i, d in enumerate(dates)}

    # ── 종목별 일별 수익률(선계산)
    rets = defaultdict(dict)
    for c in px:
        ds = sorted(px[c])
        for a, b in zip(ds, ds[1:]):
            x, y = px[c][a], px[c][b]
            if x and y:
                rets[c][b] = (y / x - 1) * 100

    def risk(c, i, k, kind):
        """선정일 d=dates[i] 까지의 위험 지표. 룩어헤드 없음."""
        v = []
        for j in range(max(1, i - k + 1), i + 1):
            r = rets[c].get(dates[j])
            if r is not None:
                v.append(r)
        if len(v) < max(5, k // 3):
            return None
        if kind == 'vol':
            return statistics.stdev(v)
        if kind == 'dsd':                       # 하방편차
            d = [x for x in v if x < 0]
            return (sum(x * x for x in d) / len(v)) ** 0.5 if d else 0.0
        if kind == 'mad':                       # 평균절대편차
            m = statistics.mean(v)
            return sum(abs(x - m) for x in v) / len(v)
        if kind == 'beta':                      # 벤치 회귀 베타
            bv = [rets[L.BENCH].get(dates[j]) for j in range(max(1, i - k + 1), i + 1)]
            pair = [(a, b) for a, b in zip(v, bv) if b is not None]
            if len(pair) < 10:
                return None
            xs = [b for _, b in pair]
            ys = [a for a, _ in pair]
            mx, my = statistics.mean(xs), statistics.mean(ys)
            den = sum((x - mx) ** 2 for x in xs)
            return (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den) if den else None
        if kind == 'rng':                       # 최대 일간 절대변동
            return max(abs(x) for x in v)
        return None

    def run(select):
        out = []
        for i, d in enumerate(dates[:-1]):
            nxt = dates[i + 1]
            cd = cands.get(d)
            if not cd or len(cd) < L.NPICK:
                continue
            picks = select(cd, i, d)
            rs = [L.fwd(px, c, d, nxt) for c in picks]
            rs = [x for x in rs if x is not None]
            if len(rs) < L.NPICK:
                continue
            out.append((d, sum(rs) / len(rs)))
        return out

    def sel_mom(cd, i, d):
        return [c for _, c in cd[:L.NPICK]]

    def sel_lv(pool, k=20, kind='vol', hi=False):
        def f(cd, i, d):
            sc = []
            for _, c in cd[:pool]:
                v = risk(c, i, k, kind)
                if v is not None:
                    sc.append((v, c))
            if len(sc) < L.NPICK:
                return sel_mom(cd, i, d)
            sc.sort(reverse=hi)
            return [c for _, c in sc[:L.NPICK]]
        return f

    def bench_series(idx):
        return [(d, r) for d, r in ((dates[i + 1], rets[L.BENCH].get(dates[i + 1]))
                                    for i in range(len(dates) - 1)) if r is not None]

    base_r = run(sel_mom)
    keys = [d for d, _ in base_r]
    base = prof([x for _, x in base_r], 'MOM (확정방법)')
    bmk = prof([rets[L.BENCH][d] for d in
                (dates[pos[k] + 1] for k in keys)], 'KODEX200')
    print(f'채점 {base["n"]}일 ({keys[0]}~{keys[-1]})\n')
    show(base)
    show(bmk, base)
    print()

    print('=== R1 파라미터 고원 — pool × 변동성 룩백 k ===')
    print(f'  {"":8s}' + ''.join(f'{"k"+str(k):>22s}' for k in (10, 20, 40, 60)))
    grid = {}
    for pool in (10, 15, 20, 25, 30, 40, 50):
        row = f'  pool{pool:<4d}'
        for k in (10, 20, 40, 60):
            p = prof([x for _, x in run(sel_lv(pool, k))], '')
            grid[(pool, k)] = p
            ok = (p['cagr'] > base['cagr'] - 1 and p['mdd'] > base['mdd'] + 5
                  and p['sharpe'] > base['sharpe'])
            row += f'  CAGR{p["cagr"]:+5.1f} MDD{p["mdd"]:6.1f}{"✔" if ok else " "}'
        print(row)
    npass = sum(1 for p in grid.values()
                if p['cagr'] > base['cagr'] - 1 and p['mdd'] > base['mdd'] + 5
                and p['sharpe'] > base['sharpe'])
    print(f'  격자 28점 중 승격조건(CAGR≥base-1%p · MDD 5%p+ 개선 · Sharpe 개선) 통과 {npass}점')

    CAND = sel_lv(30, 20)
    cand_r = run(CAND)
    cand = prof([x for _, x in cand_r], 'LV pool30 k20')
    print()
    show(cand, base)

    print('\n=== R2 fold — 3분할·6분할 (누적·MDD 각각) ===')
    n = len(cand_r)
    for K in (3, 6):
        print(f'  [{K}분할]')
        okc = okm = 0
        for i in range(K):
            lo, hi = i * n // K, (i + 1) * n // K
            m = prof([x for _, x in base_r[lo:hi]], '')
            l = prof([x for _, x in cand_r[lo:hi]], '')
            okc += l['cum'] > m['cum']
            okm += l['mdd'] > m['mdd']
            print(f'    fold{i+1} MOM 누적{m["cum"]:+7.1f}% MDD{m["mdd"]:6.1f}% | '
                  f'LV 누적{l["cum"]:+7.1f}% MDD{l["mdd"]:6.1f}%')
        print(f'    → 누적 우위 {okc}/{K} · MDD 우위 {okm}/{K}')

    print('\n=== R3 정의 교체 — 위험 척도를 바꿔도 재현되는가 (pool30 k20) ===')
    for kind, nm in [('vol', '표준편차'), ('dsd', '하방편차'), ('mad', '평균절대편차'),
                     ('beta', '벤치베타'), ('rng', '최대일간변동')]:
        p = prof([x for _, x in run(sel_lv(30, 20, kind))], f'LV {nm}')
        show(p, base)
    p = prof([x for _, x in run(sel_lv(30, 20, 'vol', hi=True))], 'LV(대조) 고변동 5종')
    show(p, base)

    print('\n=== R4 플라시보 — pool30 중 무작위 5종 200회 (분산효과 분리) ===')
    rng = random.Random(20260819)
    nullc, nullm, nulls = [], [], []
    for _ in range(200):
        def g(cd, i, d, rng=rng):
            sub = [c for _, c in cd[:30]]
            return rng.sample(sub, L.NPICK) if len(sub) >= L.NPICK else sel_mom(cd, i, d)
        p = prof([x for _, x in run(g)], '')
        nullc.append(p['cagr']); nullm.append(p['mdd']); nulls.append(p['sharpe'])
    nullc.sort(); nullm.sort(); nulls.sort()
    print(f'  귀무 CAGR   중앙 {nullc[99]:+6.1f}% · 95분위 {nullc[189]:+6.1f}%  |  실제 {cand["cagr"]:+6.1f}%'
          f'  → p={sum(1 for x in nullc if x>=cand["cagr"])/200:.3f}')
    print(f'  귀무 MDD    중앙 {nullm[99]:6.1f}% · 95분위(양호) {nullm[189]:6.1f}%  |  실제 {cand["mdd"]:6.1f}%'
          f'  → p={sum(1 for x in nullm if x>=cand["mdd"])/200:.3f}')
    print(f'  귀무 Sharpe 중앙 {nulls[99]:5.2f} · 95분위 {nulls[189]:5.2f}  |  실제 {cand["sharpe"]:5.2f}'
          f'  → p={sum(1 for x in nulls if x>=cand["sharpe"])/200:.3f}')

    print('\n=== R5 꼬리 — 최악/최고 k일 제거 시 (LV−MOM 일별 차) ===')
    diff = [c - m for (_, c), (_, m) in zip(cand_r, base_r)]
    s = sorted(diff, reverse=True)
    tot = sum(s)
    print(f'  평균 차 {tot/n:+.4f}%p · 중앙값 {statistics.median(diff):+.4f}%p')
    for k in (1, 3, 5, 10, 20):
        print(f'    상위 {k:2d}일 제거 {(tot-sum(s[:k]))/(n-k):+.4f}  |  '
              f'하위 {k:2d}일 제거 {(tot-sum(s[-k:]))/(n-k):+.4f}')
    # 복리 기준 꼬리: 최악 k일을 baseline 으로 대체했을 때 MDD 가 유지되는가
    order = sorted(range(n), key=lambda i: diff[i])
    for k in (5, 10, 20):
        v = [x for _, x in cand_r]
        for i in order[-k:]:
            v[i] = base_r[i][1]
        p = prof(v, '')
        print(f'    최고기여 {k:2d}일을 MOM 으로 대체 → CAGR{p["cagr"]:+6.1f}% MDD{p["mdd"]:7.1f}% '
              f'Sharpe{p["sharpe"]:5.2f}')

    print('\n=== 연도별 (pool30 k20) ===')
    yb = defaultdict(list)
    for (d, m), (_, l) in zip(base_r, cand_r):
        yb[d[:4]].append((m, l))
    for y in sorted(yb):
        v = yb[y]
        m = prof([a for a, _ in v], '')
        l = prof([b for _, b in v], '')
        print(f'  {y} MOM 누적{m["cum"]:+7.1f}% MDD{m["mdd"]:6.1f}% | '
              f'LV 누적{l["cum"]:+7.1f}% MDD{l["mdd"]:6.1f}%  '
              f'{"MDD우위" if l["mdd"]>m["mdd"] else "      "}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
