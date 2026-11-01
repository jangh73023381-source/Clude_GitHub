# -*- coding: utf-8 -*-
"""2026-09-05 — 비대칭 ATR 밴드 최선안(B: 하단 -0.5% 고정 / 상단 b x ATR)에 R1·R2·R5 적용."""
import os, sys, json, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bt_atr_cb_asym_20260905 import (load, build_atr, top5_by_day, run, stat)

HERE = os.path.dirname(os.path.abspath(__file__))


def tstat(v):
    mu = statistics.mean(v); sd = statistics.stdev(v)
    return mu, mu / (sd / len(v) ** 0.5)


def main():
    bar, nm, dates = load()
    di = {d: i for i, d in enumerate(dates)}
    tops = top5_by_day(bar, dates, di)
    codes = {c for v in tops.values() for c in v}
    atr = build_atr(bar, dates, di, codes, lag=0)

    fix, ddf, _ = run(bar, dates, di, tops, atr, lambda c, a: -0.5 <= c <= 1.5)

    print('[R1] 파라미터 고원 — B계열 상단 b x ATR (하단 -0.5% 고정)')
    print(f'  {"b":>6s}{"평균초과":>10s}{"t":>8s}{"진입":>7s}{"vs 고정":>10s}')
    print('  ' + '-' * 41)
    grid = {}
    for b_ in (0.05, 0.10, 0.125, 0.15, 0.175, 0.20, 0.225, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.80):
        v, dd, nb = run(bar, dates, di, tops, atr, lambda c, a, b_=b_: -0.5 <= c and c / a <= b_)
        mu, t = tstat(v)
        grid[b_] = (v, dd)
        print(f'  {b_:6.3f}{mu:+10.4f}{t:8.2f}{nb:7d}{mu - statistics.mean(fix):+10.4f}')

    best = max(grid, key=lambda k: statistics.mean(grid[k][0]))
    v, dd = grid[best]
    print(f'\n  → 최선 b={best}')

    # 페어(같은 날짜)로 차 시계열
    fmap = dict(zip(ddf, fix)); vmap = dict(zip(dd, v))
    common = sorted(set(fmap) & set(vmap))
    diff = [vmap[d] - fmap[d] for d in common]
    mu, t = tstat(diff)
    print(f'\n[페어] 같은 날짜 {len(common)}일 · 비대칭 − 고정 = {mu:+.4f}%p/일 · t={t:.2f} · '
          f'이긴날 {sum(1 for x in diff if x>0)/len(diff):.1%}')

    print('\n[R2] 3분할 fold (페어 차, 전·중·후)')
    n = len(common); k = n // 3
    for i, (s, e) in enumerate([(0, k), (k, 2 * k), (2 * k, n)], 1):
        seg = diff[s:e]
        m2, t2 = tstat(seg)
        print(f'  fold{i} {common[s]}~{common[e-1]}  {m2:+9.4f}  t={t2:5.2f}  '
              f'{"통과" if m2 > 0 else "미달"}')

    print('\n[R5] 꼬리 기여도 (페어 차)')
    sv = sorted(diff, reverse=True)
    tot = sum(diff)
    for k_ in (1, 3, 5, 10):
        rem = sv[k_:]
        print(f'  상위 {k_:2d}일 제거 → 평균 {statistics.mean(rem):+.4f}%p  '
              f'(기여율 {sum(sv[:k_])/tot*100 if tot else 0:6.1f}%)  '
              f'{"부호유지" if statistics.mean(rem) > 0 else "★부호반전"}')
    print(f'  중앙값 차 {statistics.median(diff):+.4f}%p')
    srt = sorted(diff); w = int(len(srt) * 0.05)
    wins = srt[w:len(srt) - w] if w else srt
    print(f'  윈저화(5%) 평균 {statistics.mean(wins):+.4f}%p')

    # 절대 수준 R5 (고정 밴드 자체가 벤치 대비 얼마나 꼬리 의존인가)
    print('\n[참고] 고정 밴드 자체의 꼬리 의존 (벤치 대비)')
    sf = sorted(fix, reverse=True); tf = sum(fix)
    for k_ in (1, 3, 5, 10):
        print(f'  상위 {k_:2d}일 제거 → 평균 {statistics.mean(sf[k_:]):+.4f}%p  '
              f'(기여율 {sum(sf[:k_])/tf*100 if tf else 0:6.1f}%)')
    print(f'  중앙값 {statistics.median(fix):+.4f}%p')

    # D-1 ATR 민감도
    print('\n[민감도] ATR 을 D-1 까지로 계산 (조달 보수)')
    atr1 = build_atr(bar, dates, di, codes, lag=1)
    v1, dd1, nb1 = run(bar, dates, di, tops, atr1, lambda c, a: -0.5 <= c and c / a <= best)
    m1, t1 = tstat(v1)
    print(f'  b={best} (D-1 ATR)  {m1:+.4f}%p  t={t1:.2f}  진입 {nb1}')


if __name__ == '__main__':
    main()
