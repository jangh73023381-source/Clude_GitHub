# -*- coding: utf-8 -*-
"""2026-08-03 루프 3~5단계 — iteration 1: Rule DD(지수 드로다운 조건부 역모멘텀 스위치).

동기: 2026-07-31 채점에서 트랙 A가 코스피 대비 -17.057%p로 표본 내 최악을 기록했다.
7/28~7/30 사흘간 코스피가 7,096 → 5,594(-21.2%)로 붕괴한 직후 7/31에 +17.91%
(KODEX200 +24.17%) V자 반등이 나왔고, 그날 상위10%(컷오프 +27.42%)는 반도체·지수·
AI 등 '가장 많이 빠졌던 고베타'가 독식했다. 방어(은행·고배당) 5종은 +0.85%에 그쳤다.
mom20 상위는 급락장에서 구조적으로 방어자산에 고착되므로, **반등일에 정확히 반대
방향을 향한다**는 것이 이번 실패의 본질이다.

가설: 지수가 20일 최고가 대비 일정 폭 이상 무너져 있는 국면(D 시점 관측 가능)에서는
mom20 상위가 아니라 **mom20 하위(낙폭과대)** 를 골라야 한다 — 즉 국면에 따라 선정축의
'부호'를 뒤집는다.

금지(중복)목록과의 구별:
 · Rule R'/regime 게이팅(7/26·7/29) — MA20/60 추세·r60±3% 밴드로 '국면'을 정의하고
   비중을 낮추거나 중기(H=20) 평균회귀를 봤다. DD는 (a) 추세가 아니라 20일 고점 대비
   **낙폭 깊이**, (b) 비중이 아니라 **선정축 부호 반전**, (c) H=1 단기 트랙이라 다르다.
 · Rule MRV(전일역전 우선 재정렬) — 상시 적용이고 풀 내부 재정렬. DD는 조건부 전면 교체.
 · Rule RG(미국 리스크온 게이트) — 입력이 미국 야간 지표, 행동이 벤치마크 전환.
   DD는 입력이 국내 지수 낙폭, 행동이 역모멘텀 픽. 참고로 DD-B(벤치 전환)는 RG와
   행동이 겹치므로 진단용으로만 병기하고 승격 후보로 세지 않는다.
 · 중기 평균회귀 계열(7/29 기각) — H=20 보유. 본 검정은 H=1.

1차 지표 = v2.3 P&L (픽5 동일가중 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과일 때만 후보 승격 → 이후 잭나이프.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0731.csv')
B.MINP = 0          # 2026-07-30 최소가격 필터 폐지 반영 (선정·채점 정합)

BENCH = '069500'


def idx_dd(px, d, di, dates, k=20):
    """벤치마크(KODEX200)의 D 종가 / 최근 k거래일 최고 종가 - 1. D까지 정보만."""
    i = di[d]
    lo = max(0, i - k + 1)
    vals = [px[BENCH][dates[j]] for j in range(lo, i + 1) if dates[j] in px[BENCH]]
    cur = px[BENCH].get(d)
    if not vals or cur is None:
        return None
    hi = max(vals)
    return cur / hi - 1.0 if hi else None


def dd_flip(cand, px=None, d=None, di=None, dates=None, th=-0.08, k=20, **_):
    """DD — 지수 낙폭이 th 이하이면 mom20 '하위' 5종, 아니면 평소대로 상위 5종."""
    dd = idx_dd(px, d, di, dates, k)
    srt = sorted(cand, key=lambda x: -x['mom'])
    if dd is not None and dd <= th:
        return [x['code'] for x in srt[-5:]]
    return [x['code'] for x in srt[:5]]


def dd_bench(cand, px=None, d=None, di=None, dates=None, th=-0.08, k=20, **_):
    """DD-B(진단용) — 낙폭 국면이면 벤치마크 1종으로 전환. Rule RG와 행동이 겹친다."""
    dd = idx_dd(px, d, di, dates, k)
    srt = sorted(cand, key=lambda x: -x['mom'])
    if dd is not None and dd <= th:
        return [BENCH] * 5 if BENCH in px else [x['code'] for x in srt[:5]]
    return [x['code'] for x in srt[:5]]


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    print(f'패널 {os.path.basename(B.PANEL)} · 거래일 {len(dates)} · {dates[0]}~{dates[-1]}')

    # 발동 빈도 먼저 — 발동일이 너무 적으면 no-op이라 승격 자체가 무의미하다.
    for th in (-0.05, -0.08, -0.12, -0.15):
        n = sum(1 for d in dates[20:-1]
                if (v := idx_dd(px, d, di, dates)) is not None and v <= th)
        print(f'  DD 임계 {th*100:+.0f}% 발동일 {n}일 / {len(dates[20:-1])}일')

    variants = [
        ('baseline mom20+RuleH', B.base_sel, {}),
        ('DD1 낙폭 -5% → mom20 하위5', dd_flip, {'th': -0.05}),
        ('DD2 낙폭 -8% → mom20 하위5', dd_flip, {'th': -0.08}),
        ('DD3 낙폭 -12% → mom20 하위5', dd_flip, {'th': -0.12}),
        ('DD4 낙폭 -15% → mom20 하위5', dd_flip, {'th': -0.15}),
        ('DD5 낙폭 -8%(60일고점) → 하위5', dd_flip, {'th': -0.08, 'k': 60}),
        ('[진단] DD-B 낙폭 -8% → 벤치전환', dd_bench, {'th': -0.08}),
    ]
    B.report('iteration 1 — Rule DD 지수 드로다운 조건부 역모멘텀',
             variants, px, name, dates, di, fo, ins)


if __name__ == '__main__':
    main()
