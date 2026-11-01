# -*- coding: utf-8 -*-
"""2026-07-31 루프 3~5단계 — iteration 1: Rule CP(가격채널 위치 틸트).

동기: 7/30 채점에서 유일한 미달이 132030 KODEX 골드선물(순위 35/187)이었고,
그날 상위10%는 조선·2차전지·방산 등 '낙폭과대 후 재가속' 종목이 장악했다.
2026-07-26 섹터대표종목 백테스트(보고서 5절)에서 6개월 가격채널 위치가
0.80~0.95(저항선 직하)면 최강·0.40~0.60(중간)이면 최약이라는 순서가 5개 룩백
전부에서 확인됐으나, 이 축은 **단기 ETF 트랙에는 한 번도 적용된 적이 없다**.

금지(중복)목록과의 구별: Rule O/P/H/G·저변동 틸트(방어자산 게이팅), Rule S(모멘텀
가속도), Rule T(mom20 극단치컷), Rule Q(섹터캡)/TD(테마집중도), X/XC(수급),
ST/STR/UX(픽 고착), RS(코스피·코스닥 상대강도), FF, L/M/N, 신선한 붕괴 제외.
Rule CP는 mom20 값이 아니라 **자기 자신의 과거 고저 레인지 내 상대 위치**를 쓰므로
위 어느 계열과도 입력이 다르다.

1차 지표 = v2.3 P&L (픽5 동일가중 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test 3개 모두 baseline 초과일 때만 후보 승격 → 3분할·잭나이프.
룩어헤드 금지 — 선정은 D 종가까지의 정보만 사용.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0730.csv')
B.MINP = 0          # 2026-07-30 최소가격 필터 폐지 반영 (선정·채점 정합)


def chpos(px, c, d, di, dates, k=120):
    """6개월(120거래일) 종가 채널 내 위치 0~1. 데이터 부족·레인지 0이면 None."""
    i = di[d]
    lo_i = max(0, i - k + 1)
    vals = [px[c][dates[j]] for j in range(lo_i, i + 1) if dates[j] in px[c]]
    if len(vals) < 40:
        return None
    lo, hi, cur = min(vals), max(vals), px[c].get(d)
    if cur is None or hi <= lo:
        return None
    return (cur - lo) / (hi - lo)


def cp_drop_mid(cand, px=None, d=None, di=None, dates=None, clo=0.40, chi=0.60, **_):
    """CP1 — 채널위치 중간구간(최약) 종목 제외 후 mom20 상위5."""
    keep = []
    for x in cand:
        p = chpos(px, x['code'], d, di, dates)
        if p is not None and clo <= p <= chi:
            continue
        keep.append(x)
    if len(keep) < 5:
        keep = cand
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


def cp_rank(cand, px=None, d=None, di=None, dates=None, pool=15, **_):
    """CP2 — mom20 상위 pool 안에서 채널위치 상위5."""
    top = sorted(cand, key=lambda x: -x['mom'])[:pool]
    sc = [(p, x['code']) for x in top
          if (p := chpos(px, x['code'], d, di, dates)) is not None]
    if len(sc) < 5:
        return B.base_sel(cand)
    sc.sort(reverse=True)
    return [c for _, c in sc[:5]]


def cp_band_first(cand, px=None, d=None, di=None, dates=None, clo=0.80, chi=0.95, **_):
    """CP3 — 채널위치 0.80~0.95(최강 구간)를 우선 채우고 부족분만 mom20 순 충원."""
    srt = sorted(cand, key=lambda x: -x['mom'])
    band = [x['code'] for x in srt
            if (p := chpos(px, x['code'], d, di, dates)) is not None and clo <= p <= chi]
    out = band[:5]
    for x in srt:
        if len(out) >= 5:
            break
        if x['code'] not in out:
            out.append(x['code'])
    return out


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    print(f'패널 {os.path.basename(B.PANEL)} · 거래일 {len(dates)} · {dates[0]}~{dates[-1]}')

    variants = [
        ('baseline mom20+RuleH', B.base_sel, {}),
        ('CP1 중간구간(0.40~0.60) 제외', cp_drop_mid, {}),
        ('CP1b 중간구간(0.35~0.65) 제외', cp_drop_mid, {'clo': 0.35, 'chi': 0.65}),
        ('CP2 mom20 top15 → 채널위치 상위5', cp_rank, {}),
        ('CP2b mom20 top20 → 채널위치 상위5', cp_rank, {'pool': 20}),
        ('CP3 0.80~0.95 우선 충원', cp_band_first, {}),
        ('CP3b 0.70~0.95 우선 충원', cp_band_first, {'clo': 0.70}),
    ]
    B.report('iteration 1 — Rule CP 가격채널 위치', variants, px, name, dates, di, fo, ins)


if __name__ == '__main__':
    main()
