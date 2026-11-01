# -*- coding: utf-8 -*-
"""2026-07-31 루프 iteration 5 — Rule CR(실현 상관 기반 분산 선택).

구별: 기각된 Rule Q(섹터분산상한)·TD(테마 집중도)는 **테마 라벨**을 입력으로 썼다.
CR은 라벨을 전혀 쓰지 않고 **최근 20일 일간수익률의 실현 상관행렬**만 보고
mom20 상위 풀에서 서로 덜 붙어 움직이는 5종을 그리디로 고른다. 라벨 오분류·
테마 경계 문제에 영향받지 않는다는 점에서 입력이 다르다.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0730.csv')
B.MINP = 0


def rets(px, c, d, di, dates, k=20):
    i = di[d]
    if i < k:
        return None
    out = []
    for j in range(i - k + 1, i + 1):
        a, b = px[c].get(dates[j - 1]), px[c].get(dates[j])
        if not (a and b):
            return None
        out.append(b / a - 1.0)
    return out


def corr(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return 0.0 if da == 0 or db == 0 else num / (da * db)


def cr_sel(cand, px=None, d=None, di=None, dates=None, pool=15, cap=0.90, **_):
    top = sorted(cand, key=lambda x: -x['mom'])[:pool]
    rs = {}
    for x in top:
        r = rets(px, x['code'], d, di, dates)
        if r:
            rs[x['code']] = r
    order = [x['code'] for x in top if x['code'] in rs]
    if len(order) < 5:
        return B.base_sel(cand)
    sel = []
    for c in order:
        if len(sel) >= 5:
            break
        if all(corr(rs[c], rs[s]) <= cap for s in sel):
            sel.append(c)
    for c in order:                      # 상한 때문에 5종을 못 채우면 mom20 순 충원
        if len(sel) >= 5:
            break
        if c not in sel:
            sel.append(c)
    return sel[:5]


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    variants = [
        ('baseline mom20+RuleH', B.base_sel, {}),
        ('CR cap 0.90 / pool15', cr_sel, {}),
        ('CR cap 0.80 / pool15', cr_sel, {'cap': 0.80}),
        ('CR cap 0.70 / pool15', cr_sel, {'cap': 0.70}),
        ('CR cap 0.80 / pool25', cr_sel, {'cap': 0.80, 'pool': 25}),
    ]
    B.report('iteration 5 — Rule CR 실현상관 분산', variants, px, name, dates, di, {}, {})


if __name__ == '__main__':
    main()
