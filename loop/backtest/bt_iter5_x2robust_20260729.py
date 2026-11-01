# -*- coding: utf-8 -*-
"""2026-07-29 루프 iteration 5 — X2(외국인 비중 감소종목 제외) 강건성 검정.

iteration 3에서 X2가 full +0.3110 / train +0.2938 / test +0.3276 (baseline
+0.1735 / +0.0072 / +0.3350) 로 **test만 -0.007%p 차이로 2분할 가드에 걸렸다.**
근소한 미달이 진짜 신호인지 잡음인지 가르기 위해 더 엄격한 검정을 건다:
  (a) 3분할(3-fold) 전 구간 우위, (b) 일자 잭나이프(1일 제거) 하한,
  (c) 발동일(픽이 실제로 바뀐 날)만 모은 조건부 성과,
  (d) 임계값 민감도(감소 허용폭 스윕) — 고원이 있는지.
통과해야 shadow 등재 후보, 미통과면 기각.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from bt_iter2_3_20260729 import (  # noqa: E402
    BENCH, COST, base_sel, build_cand, flow_score, load_flow, load_panel,
)


def x2_sel(cand, fo, d, di, dates, tol=0.0):
    keep = []
    for x in cand:
        s = flow_score(fo, x['code'], d, di, dates, 5, 'level')
        if s is not None and s < -tol:
            continue
        keep.append(x)
    if len(keep) < 5:
        keep = cand
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


def series(px, name, dates, di, fo, tol=None, hi=None):
    """(날짜, baseline 초과, 변형 초과, 픽변경여부) 리스트."""
    out = []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        if hi and d > hi:
            continue
        cand = build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        ba, bb = px[BENCH].get(d), px[BENCH].get(nxt)
        if not (ba and bb):
            continue
        bench = bb / ba - 1.0

        def ret(picks):
            r = [px[c][nxt] / px[c][d] - 1.0 for c in picks
                 if px[c].get(d) and px[c].get(nxt)]
            return (sum(r) / len(r) - COST - bench) * 100 if r else None

        p0 = base_sel(cand)
        p1 = p0 if tol is None else x2_sel(cand, fo, d, di, dates, tol)
        r0, r1 = ret(p0), ret(p1)
        if r0 is None or r1 is None:
            continue
        out.append((d, r0, r1, set(p0) != set(p1)))
    return out


def folds(vals, k):
    n = len(vals)
    return [vals[i * n // k:(i + 1) * n // k] for i in range(k)]


def main():
    px, name, dates = load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, _ = load_flow()
    hi = max(d for c in fo for d in fo[c])
    s = series(px, name, dates, di, fo, tol=0.0, hi=hi)
    base = [x[1] for x in s]
    var = [x[2] for x in s]
    fired = [i for i, x in enumerate(s) if x[3]]
    print(f'표본 {len(s)}일 ({s[0][0]}~{s[-1][0]}) · 발동(픽변경) {len(fired)}일')
    print(f'baseline 평균 {statistics.mean(base):+.4f} · X2 평균 {statistics.mean(var):+.4f}')

    print('\n(a) 3분할 전 구간 우위')
    ok3 = True
    for i, (fb, fv) in enumerate(zip(folds(base, 3), folds(var, 3)), 1):
        mb, mv = statistics.mean(fb), statistics.mean(fv)
        win = mv > mb
        ok3 &= win
        print(f'  fold{i} (n={len(fb)}) baseline {mb:+.4f} · X2 {mv:+.4f} → {"우위" if win else "열위"}')
    print(f'  → 3분할 판정: {"통과" if ok3 else "미통과"}')

    print('\n(b) 일자 잭나이프 (1일 제거 시 X2-baseline 차이 하한)')
    diff = [v - b for b, v in zip(base, var)]
    jk = [statistics.mean(diff[:i] + diff[i + 1:]) for i in range(len(diff))]
    print(f'  차이 평균 {statistics.mean(diff):+.4f} · 잭나이프 하한 {min(jk):+.4f} · 상한 {max(jk):+.4f}')
    print(f'  → 부호 유지: {"예" if min(jk) > 0 else "아니오"}')

    print('\n(c) 발동일 조건부 성과')
    if fired:
        fb = [base[i] for i in fired]
        fv = [var[i] for i in fired]
        print(f'  발동 {len(fired)}일 · baseline {statistics.mean(fb):+.4f} · X2 {statistics.mean(fv):+.4f}'
              f' · 차이 {statistics.mean(fv) - statistics.mean(fb):+.4f}')
        print(f'  → v2.2 B 발동일 5일↑ 요건: {"충족" if len(fired) >= 5 else "미충족"}')
    else:
        print('  발동일 0 — no-op')

    print('\n(d) 임계값 민감도 (감소 허용폭 tol, 고원 여부)')
    for tol in (0.0, 0.02, 0.05, 0.10, 0.20):
        ss = series(px, name, dates, di, fo, tol=tol, hi=hi)
        v = [x[2] for x in ss]
        b = [x[1] for x in ss]
        nf = sum(1 for x in ss if x[3])
        print(f'  tol={tol:.2f}  X2 {statistics.mean(v):+.4f}  (baseline {statistics.mean(b):+.4f})'
              f'  발동 {nf}일  차이 {statistics.mean(v) - statistics.mean(b):+.4f}')


if __name__ == '__main__':
    main()
