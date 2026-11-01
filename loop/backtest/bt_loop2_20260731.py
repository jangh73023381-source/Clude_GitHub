# -*- coding: utf-8 -*-
"""2026-07-31 루프 iteration 2 — Rule SK(스킵 모멘텀): 랭킹 입력 자체를 바꾼다.

동기: 학술 모멘텀은 최근 1개월을 건너뛴 t-12~t-2 수익률을 쓴다(단기 반전 회피).
현행 v1.9는 D 종가까지의 20일 수익률을 그대로 쓰므로 **선정 직전 며칠의 급등이
랭킹에 그대로 반영**되고, 그 급등이 익일 되돌림으로 이어지면 손해가 된다.

구별: Rule L(cum3 되돌림 '필터')·Rule S(모멘텀 가속도)·Rule T(극단치 컷)·'신선한
붕괴 제외'는 전부 mom20 랭킹은 그대로 두고 후보를 걸러내는 방식이었다. SK는
**랭킹 계산식 자체를 교체**하므로 입력이 다르다(N 대장에 별도 계상).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0730.csv')
B.MINP = 0


def skip_mom(px, c, d, di, dates, k=20, s=2):
    """D-s 시점까지의 k일 수익률 — 최근 s일을 랭킹에서 제외한다."""
    i = di[d]
    if i < k + s:
        return None
    a, b = px[c].get(dates[i - k - s]), px[c].get(dates[i - s])
    return (b / a - 1.0) if (a and b) else None


def sk_sel(cand, px=None, d=None, di=None, dates=None, k=20, s=2, **_):
    sc = []
    for x in cand:
        m = skip_mom(px, x['code'], d, di, dates, k, s)
        if m is not None:
            sc.append((m, x['code']))
    if len(sc) < 5:
        return B.base_sel(cand)
    sc.sort(reverse=True)
    return [c for _, c in sc[:5]]


def blend_sel(cand, px=None, d=None, di=None, dates=None, k=20, s=2, w=0.5, **_):
    """SK와 현행 mom20의 순위 가중 블렌드(w=SK 비중)."""
    srt = sorted(cand, key=lambda x: -x['mom'])
    r1 = {x['code']: i for i, x in enumerate(srt)}
    sc = [(m, x['code']) for x in cand
          if (m := skip_mom(px, x['code'], d, di, dates, k, s)) is not None]
    if len(sc) < 5:
        return B.base_sel(cand)
    sc.sort(reverse=True)
    r2 = {c: i for i, (_, c) in enumerate(sc)}
    both = [c for c in r1 if c in r2]
    both.sort(key=lambda c: w * r2[c] + (1 - w) * r1[c])
    return both[:5]


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    variants = [
        ('baseline mom20+RuleH', B.base_sel, {}),
        ('SK1 skip1 (D-1까지 20일)', sk_sel, {'s': 1}),
        ('SK2 skip2 (D-2까지 20일)', sk_sel, {'s': 2}),
        ('SK3 skip3 (D-3까지 20일)', sk_sel, {'s': 3}),
        ('SK2w 랭킹블렌드 w=0.5 (skip2)', blend_sel, {'s': 2, 'w': 0.5}),
        ('SK1w 랭킹블렌드 w=0.3 (skip1)', blend_sel, {'s': 1, 'w': 0.3}),
    ]
    B.report('iteration 2 — Rule SK 스킵 모멘텀', variants, px, name, dates, di, fo, ins)


if __name__ == '__main__':
    main()
