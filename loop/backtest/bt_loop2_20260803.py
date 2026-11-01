# -*- coding: utf-8 -*-
"""2026-08-03 루프 3~5단계 — iteration 2~5 (distinct 4축).

iteration 1(Rule DD, 드로다운 조건부 역모멘텀)이 3분할 가드 전부 미통과로 기각된 뒤,
검증관 반송에 따라 서로 다른 4개 축을 이어서 검정한다. 공통 동기는 동일하다 —
2026-07-31 V자 반등(+17.91%)에서 방어 고착 5종이 -17.057%p로 무너진 실패.

 · iteration 2 Rule LS — 지수 **연속 하락일수**(streak) 조건부 역모멘텀 스위치.
   DD는 낙폭 '크기', LS는 '지속 길이'를 쓴다(같은 날에도 값이 다르게 움직인다).
 · iteration 3 Rule RB — 지수가 크게 오른 날 **반등 참여도**로 후보를 거른다.
   D일 지수 대비 초과 상승한 종목만 남겨 '반등에서 못 따라가는' 픽을 배제.
 · iteration 4 Rule EW — 픽5 중 **1슬롯을 벤치마크(KODEX200)로 상시 고정**.
   Rule RG(조건부 전면 전환)와 달리 상시·부분이라 발동일 개념이 없다.
 · iteration 5 Rule DS — 유니버스 **횡단면 분산(당일 수익률 표준편차)** 이 확대된
   국면에서만 mom20 풀을 넓혀(top5→top20 중 낙폭 깊은 5종) 고른다.

1차 지표 = v2.3 P&L (픽5 동일가중 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과일 때만 후보 승격.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0731.csv')
B.MINP = 0

BENCH = '069500'


def bench_ret(px, d, di, dates, k=1):
    i = di[d]
    if i < k:
        return None
    a, b = px[BENCH].get(dates[i - k]), px[BENCH].get(d)
    return (b / a - 1.0) if (a and b) else None


def down_streak(px, d, di, dates, cap=10):
    """D까지 벤치마크가 연속으로 하락한 거래일 수."""
    i, n = di[d], 0
    while n < cap and i - 1 >= 0:
        a, b = px[BENCH].get(dates[i - 1]), px[BENCH].get(dates[i])
        if a is None or b is None or b >= a:
            break
        n += 1
        i -= 1
    return n


def disp(px, cand, d, di, dates):
    """유니버스 당일 수익률의 횡단면 표준편차."""
    rs = []
    for x in cand:
        r = B.mom(px, x['code'], d, di, dates, 1)
        if r is not None:
            rs.append(r)
    return statistics.pstdev(rs) if len(rs) > 5 else None


def ls_flip(cand, px=None, d=None, di=None, dates=None, n=3, **_):
    srt = sorted(cand, key=lambda x: -x['mom'])
    if down_streak(px, d, di, dates) >= n:
        return [x['code'] for x in srt[-5:]]
    return [x['code'] for x in srt[:5]]


def rb_filter(cand, px=None, d=None, di=None, dates=None, up=0.02, **_):
    """Rule RB — 지수가 up 이상 오른 날에는 지수보다 더 오른 종목만 후보."""
    srt = sorted(cand, key=lambda x: -x['mom'])
    br = bench_ret(px, d, di, dates)
    if br is None or br < up:
        return [x['code'] for x in srt[:5]]
    keep = [x for x in srt
            if (r := B.mom(px, x['code'], d, di, dates, 1)) is not None and r >= br]
    if len(keep) < 5:
        keep = srt
    return [x['code'] for x in keep[:5]]


def ew_bench(cand, px=None, d=None, di=None, dates=None, **_):
    srt = [x['code'] for x in sorted(cand, key=lambda x: -x['mom'])]
    out = [BENCH] if BENCH in px else []
    for c in srt:
        if len(out) >= 5:
            break
        if c not in out:
            out.append(c)
    return out


def ds_wide(cand, px=None, d=None, di=None, dates=None, mult=1.5, pool=20, **_):
    """Rule DS — 분산 확대 국면이면 mom20 top pool 중 20일 낙폭 깊은 5종."""
    srt = sorted(cand, key=lambda x: -x['mom'])
    cur = disp(px, cand, d, di, dates)
    i = di[d]
    hist = [v for j in range(max(0, i - 20), i)
            if (v := disp(px, cand, dates[j], di, dates)) is not None]
    if cur is None or not hist or cur < mult * statistics.mean(hist):
        return [x['code'] for x in srt[:5]]
    top = srt[:pool]
    sc = []
    for x in top:
        m = B.mom(px, x['code'], d, di, dates, 20)
        if m is not None:
            sc.append((m, x['code']))
    if len(sc) < 5:
        return [x['code'] for x in srt[:5]]
    sc.sort()
    return [c for _, c in sc[:5]]


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    print(f'패널 {os.path.basename(B.PANEL)} · 거래일 {len(dates)} · {dates[0]}~{dates[-1]}')

    B.report('iteration 2 — Rule LS 연속 하락일수 조건부 역모멘텀', [
        ('baseline mom20+RuleH', B.base_sel, {}),
        ('LS2 연속 2일 하락 → 하위5', ls_flip, {'n': 2}),
        ('LS3 연속 3일 하락 → 하위5', ls_flip, {'n': 3}),
        ('LS4 연속 4일 하락 → 하위5', ls_flip, {'n': 4}),
    ], px, name, dates, di, fo, ins)

    B.report('iteration 3 — Rule RB 반등 참여도 필터', [
        ('baseline mom20+RuleH', B.base_sel, {}),
        ('RB1 지수 +1%↑일 지수초과종목만', rb_filter, {'up': 0.01}),
        ('RB2 지수 +2%↑일 지수초과종목만', rb_filter, {'up': 0.02}),
        ('RB3 지수 +3%↑일 지수초과종목만', rb_filter, {'up': 0.03}),
    ], px, name, dates, di, fo, ins)

    B.report('iteration 4 — Rule EW 벤치 1슬롯 상시 고정', [
        ('baseline mom20+RuleH', B.base_sel, {}),
        ('EW1 KODEX200 1슬롯 고정', ew_bench, {}),
    ], px, name, dates, di, fo, ins)

    B.report('iteration 5 — Rule DS 분산확대 국면 낙폭선호', [
        ('baseline mom20+RuleH', B.base_sel, {}),
        ('DS1 분산 1.3배·pool20', ds_wide, {'mult': 1.3}),
        ('DS2 분산 1.5배·pool20', ds_wide, {'mult': 1.5}),
        ('DS3 분산 2.0배·pool20', ds_wide, {'mult': 2.0}),
        ('DS4 분산 1.5배·pool10', ds_wide, {'mult': 1.5, 'pool': 10}),
    ], px, name, dates, di, fo, ins)


if __name__ == '__main__':
    main()
