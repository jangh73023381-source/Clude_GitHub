# -*- coding: utf-8 -*-
"""2026-07-31 루프 iteration 3·4 — 랭킹 구성축 2종(각각 distinct).

iteration 3 · Rule VR — 변동성 정규화 모멘텀 (mom20 / 20일 실현변동성)
  구별: 기각된 '저변동 틸트'는 변동성이 낮은 종목을 **일방적으로 우대**했다.
  VR은 변동성이 높아도 그만큼 모멘텀이 크면 순위를 유지시키는 **비율 랭킹**이라
  저변동 종목을 무조건 끌어올리지 않는다(입력·방향이 다르다).

iteration 4 · Rule MB — 다중기간 모멘텀 랭크 합성 (mom5·mom20·mom60)
  구별: Rule S(가속도)는 두 기간의 '차이', Rule SK는 '창 이동'이었다. MB는
  서로 다른 세 기간의 **순위를 합산**하므로 단일 기간 왜곡에 덜 민감하다.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0730.csv')
B.MINP = 0


def realvol(px, c, d, di, dates, k=20):
    i = di[d]
    if i < k:
        return None
    rs = []
    for j in range(i - k + 1, i + 1):
        a, b = px[c].get(dates[j - 1]), px[c].get(dates[j])
        if a and b:
            rs.append(b / a - 1.0)
    if len(rs) < k // 2:
        return None
    return statistics.pstdev(rs) or None


def vr_sel(cand, px=None, d=None, di=None, dates=None, floor=0.005, **_):
    sc = []
    for x in cand:
        v = realvol(px, x['code'], d, di, dates)
        if v is None:
            continue
        sc.append((x['mom'] / max(v, floor), x['code']))
    if len(sc) < 5:
        return B.base_sel(cand)
    sc.sort(reverse=True)
    return [c for _, c in sc[:5]]


def mb_sel(cand, px=None, d=None, di=None, dates=None, ks=(5, 20, 60), **_):
    ranks = {}
    for k in ks:
        vals = []
        for x in cand:
            m = B.mom(px, x['code'], d, di, dates, k)
            if m is not None:
                vals.append((m, x['code']))
        if len(vals) < 5:
            return B.base_sel(cand)
        vals.sort(reverse=True)
        for i, (_, c) in enumerate(vals):
            ranks.setdefault(c, []).append(i)
    full = [(sum(v) / len(v), c) for c, v in ranks.items() if len(v) == len(ks)]
    if len(full) < 5:
        return B.base_sel(cand)
    full.sort()
    return [c for _, c in full[:5]]


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    variants = [
        ('baseline mom20+RuleH', B.base_sel, {}),
        ('VR 변동성정규화 모멘텀', vr_sel, {}),
        ('VRf floor 1.0%', vr_sel, {'floor': 0.010}),
        ('MB 랭크합성 5·20·60', mb_sel, {}),
        ('MBa 랭크합성 10·20·40', mb_sel, {'ks': (10, 20, 40)}),
        ('MBb 랭크합성 20·60', mb_sel, {'ks': (20, 60)}),
    ]
    B.report('iteration 3·4 — Rule VR / Rule MB', variants, px, name, dates, di, {}, {})


if __name__ == '__main__':
    main()
