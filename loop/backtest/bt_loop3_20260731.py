# -*- coding: utf-8 -*-
"""2026-07-31 iteration 2 후속 — SK1w(랭킹블렌드 w=0.3, skip1) 강건성 재검정.

1차 가드(full·train·test 3개 모두 baseline 초과)를 통과한 유일한 변형이다.
승격 여부는 (a) 3분할 전 구간 우위, (b) 일자 잭나이프 하한 > 0,
(c) 발동일(픽이 실제로 바뀐 날) 5일 이상 + 발동일 조건부 비악화로 판정한다.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402
import bt_loop2_20260731 as S  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0730.csv')
B.MINP = 0


def series(px, name, dates, di):
    out = []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = B.build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        p0 = B.base_sel(cand)
        p1 = S.blend_sel(cand, px=px, d=d, di=di, dates=dates, s=1, w=0.3)
        ba, bb = px[B.BENCH].get(d), px[B.BENCH].get(nxt)
        if not (ba and bb):
            continue
        bm = bb / ba - 1.0

        def pnl(p):
            r = [px[c][nxt] / px[c][d] - 1.0 for c in p
                 if px[c].get(d) and px[c].get(nxt)]
            return None if not r else 100 * ((sum(r) / len(r) - B.COST) - bm)
        r0, r1 = pnl(p0), pnl(p1)
        if r0 is None or r1 is None:
            continue
        out.append((d, r0, r1, set(p0) != set(p1)))
    return out


def folds(v, k):
    n = len(v)
    return [v[i * n // k:(i + 1) * n // k] for i in range(k)]


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    s = series(px, name, dates, di)
    base = [x[1] for x in s]
    var = [x[2] for x in s]
    fired = [i for i, x in enumerate(s) if x[3]]
    print(f'표본 {len(s)}일 ({s[0][0]}~{s[-1][0]}) · 발동(픽변경) {len(fired)}일')
    print(f'baseline {statistics.mean(base):+.4f} · SK1w {statistics.mean(var):+.4f}'
          f' · 차이 {statistics.mean(var) - statistics.mean(base):+.4f}')

    print('\n(a) 3분할 전 구간 우위')
    ok3 = True
    for i, (fb, fv) in enumerate(zip(folds(base, 3), folds(var, 3)), 1):
        mb, mv = statistics.mean(fb), statistics.mean(fv)
        ok3 &= mv > mb
        print(f'  fold{i} (n={len(fb)}) baseline {mb:+.4f} · SK1w {mv:+.4f}'
              f' → {"우위" if mv > mb else "열위"}')
    print(f'  → 3분할 판정: {"통과" if ok3 else "미통과"}')

    diff = [v - b for b, v in zip(base, var)]
    jk = [statistics.mean(diff[:i] + diff[i + 1:]) for i in range(len(diff))]
    print(f'\n(b) 잭나이프 하한 {min(jk):+.4f} · 상한 {max(jk):+.4f}'
          f' → 부호 유지 {"예" if min(jk) > 0 else "아니오"}')

    if fired:
        fb = [base[i] for i in fired]
        fv = [var[i] for i in fired]
        print(f'\n(c) 발동 {len(fired)}일 · baseline {statistics.mean(fb):+.4f}'
              f' · SK1w {statistics.mean(fv):+.4f}'
              f' · 차이 {statistics.mean(fv) - statistics.mean(fb):+.4f}')
        print(f'  → v2.2 B 발동일 5일↑: {"충족" if len(fired) >= 5 else "미충족"}')

    print('\n(d) w 민감도 (고원 여부)')
    for w in (0.2, 0.25, 0.3, 0.35, 0.4, 0.5):
        r = B.run(S.blend_sel, px, name, dates, di, {}, {}, s=1, w=w)
        print(f'  w={w:<5} 평균 {statistics.mean(r):+.4f}')


if __name__ == '__main__':
    main()
