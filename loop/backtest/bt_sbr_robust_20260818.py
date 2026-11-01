#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_sbr_robust_20260818.py — Rule SBR 통과 후보 1건의 4관문 강건성 검정.

후보: SBR[dart2] 업종 참여율 **하위** 5종 · pool10 · [D-1]
      full +0.2479 · train +0.2405 · test +0.2550 · jk +0.1391 (baseline full +0.1469)
      **[D-1] 이므로 실전 조달 가능**(§4-5 통과).

4관문(CLAUDE.md §4-4): R1 파라미터 고원 · R2 3분할 fold(fold3 열위 탈락) ·
R3 정의 교체 재현(dart2 ↔ yf) · R4 플라시보 순열 200회.
"""
import os, random, statistics, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_breadth_20260818 as B
import bt_sbr_20260818 as S


def folds(res, k=3):
    n = len(res)
    b = [res[i * n // k:(i + 1) * n // k] for i in range(k)]
    return [sum(x for _, x in f) / len(f) if f else 0.0 for f in b]


def main():
    px, names = B.load_etf()
    bd = B.load_breadth()
    B.BRD_DATES = sorted(bd)
    dates = sorted({d for c in px for d in px[c]})
    dates = [d for d in dates if d >= B.BRD_DATES[0]]
    codes = sorted(px)
    R_etf = S.etf_returns(px, codes, dates)
    maps = S.load_maps()
    built = {}
    for tag, smap in maps.items():
        ds, secs, ret, brd = S.sector_series(smap)
        keep = [i for i, d in enumerate(ds) if d in set(dates)]
        built[tag] = ([ds[i] for i in keep], secs, ret[keep], brd[keep])

    base_res = B.run(B.sel_base, px, names, dates, bd)
    base = B.stat(base_res, 'BASE')
    bf = folds(base_res)
    print(f'BASE full{base["mean"]:+.4f} train{base["train"]:+.4f} test{base["test"]:+.4f} '
          f'| fold {bf[0]:+.4f} {bf[1]:+.4f} {bf[2]:+.4f}\n')

    def rule(tag, pool, lag=1, direction='low', mode='level'):
        ds_s, secs, ret_s, brd_s = built[tag]
        return S.make_rule(tag, ds_s, ret_s, brd_s, R_etf, codes, lag, direction, pool, mode)

    # ── R1 파라미터 고원 (pool 축)
    print('=== R1 파라미터 고원 — pool 축 (참여율하위 · [D-1]) ===')
    for tag in ('dart2', 'yf'):
        row = f'  {tag:6s} '
        for pool in (5, 8, 10, 12, 15, 20, 25):
            s = B.stat(B.run(rule(tag, pool), px, names, dates, bd), '')
            g = '✔' if (s['mean'] > base['mean'] and s['train'] > base['train']
                        and s['test'] > base['test'] and s['jk'] > 0) else ' '
            row += f'p{pool}:{s["mean"]:+.4f}{g} '
        print(row)
    print('  (pool=5 는 개입 없음과 같다 — 후보 5종이 곧 상위 5종)')

    # ── R1b lag 축
    print('\n=== R1b lag 축 (dart2 · 참여율하위 · pool10) ===')
    for lag in (0, 1, 2, 3):
        s = B.stat(B.run(rule('dart2', 10, lag=lag), px, names, dates, bd),
                   f'lag={lag} ({"D" if lag == 0 else f"D-{lag}"})')
        B.show(s, base)

    # ── R2 3분할 fold
    print('\n=== R2 3분할 fold ===')
    for tag in ('dart2', 'yf'):
        for pool in (10, 12, 15):
            r = B.run(rule(tag, pool), px, names, dates, bd)
            s = B.stat(r, f'{tag} pool{pool}')
            fl = folds(r)
            okf = sum(1 for i in range(3) if fl[i] > bf[i])
            print(f'  {tag:6s} pool{pool:<3d} full{s["mean"]:+.4f} '
                  f'fold {fl[0]:+.4f} {fl[1]:+.4f} {fl[2]:+.4f} → baseline 초과 {okf}/3')

    # ── R3 정의 교체: 이미 위에서 dart2 ↔ yf 동시 출력. 방향 재현성만 요약
    print('\n=== R3 정의 교체 — 방향(하위 vs 상위) 재현성 [D-1] pool10 ===')
    for tag in ('dart2', 'yf'):
        lo = B.stat(B.run(rule(tag, 10, direction='low'), px, names, dates, bd), f'{tag} 하위')
        hi = B.stat(B.run(rule(tag, 10, direction='high'), px, names, dates, bd), f'{tag} 상위')
        B.show(lo, base)
        B.show(hi, base)

    # ── R4 플라시보 순열 (업종 라벨 셔플)
    print('\n=== R4 플라시보 — 업종 라벨 무작위 순열 200회 (dart2 pool10 [D-1]) ===')
    ds_s, secs, ret_s, brd_s = built['dart2']
    real = B.stat(B.run(rule('dart2', 10), px, names, dates, bd), '')['mean']
    rng = random.Random(20260818)
    nsec = brd_s.shape[1]
    null = []
    for _ in range(200):
        perm = list(range(nsec))
        rng.shuffle(perm)
        f = S.make_rule('dart2', ds_s, ret_s, brd_s[:, perm], R_etf, codes, 1, 'low', 10, 'level')
        null.append(B.stat(B.run(f, px, names, dates, bd), '')['mean'])
    null.sort()
    p = sum(1 for x in null if x >= real) / len(null)
    print(f'  실제 {real:+.4f} · 귀무 평균 {statistics.mean(null):+.4f} sd {statistics.stdev(null):.4f}')
    print(f'  귀무 분위 5%{null[9]:+.4f} 50%{null[99]:+.4f} 95%{null[189]:+.4f}')
    print(f'  경험적 p = {p:.3f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
