# -*- coding: utf-8 -*-
"""2026-07-30 루프 3~5단계 — iteration 1·2.

iteration 1 : Rule X2(외국인 보유비중 5일 감소 종목 사전제외) **재검정**.
  2026-07-29 회차에서 X2는 3분할 fold1 열위로 승격 불가였으나, 그 원인이
  `foreign_trend_panel.csv`가 20260710까지만 있어 이후 날짜가 전부 결측(=no-op)
  이었기 때문일 가능성이 남아 있었다. 오늘 패널을 20260730까지 연장했으므로
  **동일 규칙을 완전한 수급 데이터로 다시 건다**(신규 가설이 아니므로 N 미가산).

iteration 2 : 신규 distinct 축 — **외국인×기관 결합 수급**(미시도).
  X1~X4는 외국인 단독·기관 단독이었다. 결합축은 두 주체가 같은 방향일 때만
  신호로 인정한다는 점에서 구별된다.
    XC1 : 외국인 비중감소 **그리고** 기관 순매도인 종목만 제외(둘 다일 때만)
    XC2 : 외국인 비중증가 **그리고** 기관 순매수인 종목만 남김(합의 매수)
    XC3 : mom20 상위 15풀 → (외국인z + 기관z) 상위 5

1차 지표 = v2.3 P&L (픽5 동일가중 1일보유 -10bp - KODEX200), 평균 %p/일.
가드: full·train·test **3개 모두** baseline 초과일 때만 후보 승격, 이후 3분할·잭나이프.
룩어헤드 금지 — 선정은 D 종가·D까지의 수급 정보만 사용한다.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bt_iter2_3_20260729 as B  # noqa: E402

B.PANEL = os.path.join(HERE, 'panel_close_0729.csv')   # 7/28·7/29 포함으로 갱신


def zmap(vals):
    """{code: score} → {code: z}. 표준편차 0이면 전부 0."""
    if len(vals) < 3:
        return {c: 0.0 for c in vals}
    xs = list(vals.values())
    m = statistics.fmean(xs)
    sd = statistics.pstdev(xs) or 1.0
    return {c: (v - m) / sd for c, v in vals.items()}


def sel_x2(cand, px, d, di, dates, fo, ins, tol=0.0):
    keep = [x for x in cand
            if not ((s := B.flow_score(fo, x['code'], d, di, dates, 5, 'level'))
                    is not None and s < -tol)]
    if len(keep) < 5:
        keep = cand
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


def sel_xc1(cand, px, d, di, dates, fo, ins, **_):
    """외국인 감소 AND 기관 순매도 — 둘 다 부정일 때만 제외."""
    keep = []
    for x in cand:
        f = B.flow_score(fo, x['code'], d, di, dates, 5, 'level')
        g = B.flow_score(ins, x['code'], d, di, dates, 5, 'flow')
        if f is not None and g is not None and f < 0 and g < 0:
            continue
        keep.append(x)
    if len(keep) < 5:
        keep = cand
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


def sel_xc2(cand, px, d, di, dates, fo, ins, **_):
    """외국인 증가 AND 기관 순매수인 종목만 남긴다(합의 매수)."""
    keep = []
    for x in cand:
        f = B.flow_score(fo, x['code'], d, di, dates, 5, 'level')
        g = B.flow_score(ins, x['code'], d, di, dates, 5, 'flow')
        if f is not None and g is not None and f > 0 and g > 0:
            keep.append(x)
    if len(keep) < 5:
        keep = cand
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


def sel_xc3(cand, px, d, di, dates, fo, ins, pool=15, **_):
    """mom20 상위 pool → (외국인z + 기관z) 상위 5."""
    top = sorted(cand, key=lambda x: -x['mom'])[:pool]
    fs, gs = {}, {}
    for x in top:
        f = B.flow_score(fo, x['code'], d, di, dates, 5, 'level')
        g = B.flow_score(ins, x['code'], d, di, dates, 5, 'flow')
        if f is not None:
            fs[x['code']] = f
        if g is not None:
            gs[x['code']] = g
    if len(fs) < 5 or len(gs) < 5:
        return B.base_sel(cand)
    fz, gz = zmap(fs), zmap(gs)
    sc = sorted(((fz.get(x['code'], 0.0) + gz.get(x['code'], 0.0), x['code'])
                 for x in top), reverse=True)
    return [c for _, c in sc[:5]]


def daily(px, codes, d, nxt):
    """픽5 동일가중 1일보유 -10bp 후 KODEX200 대비 초과(%p)."""
    rs = []
    for c in codes:
        a, b = px[c].get(d), px[c].get(nxt)
        if a and b:
            rs.append(b / a - 1.0)
    if not rs:
        return None
    port = statistics.fmean(rs) - B.COST
    a, b = px[B.BENCH].get(d), px[B.BENCH].get(nxt)
    if not (a and b):
        return None
    return (port - (b / a - 1.0)) * 100


def series(px, name, dates, di, fo, ins, fn, **kw):
    out = []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cand = B.build_cand(px, name, d, di, dates)
        if len(cand) < 10:
            continue
        base = daily(px, B.base_sel(cand), d, nxt)
        var = daily(px, fn(cand, px, d, di, dates, fo, ins, **kw), d, nxt)
        if base is None or var is None:
            continue
        out.append((d, base, var))
    return out


def report(tag, s):
    n = len(s)
    b = statistics.fmean(x[1] for x in s)
    v = statistics.fmean(x[2] for x in s)
    k = n // 2
    bt, vt = statistics.fmean(x[1] for x in s[:k]), statistics.fmean(x[2] for x in s[:k])
    be, ve = statistics.fmean(x[1] for x in s[k:]), statistics.fmean(x[2] for x in s[k:])
    ok = (v > b) and (vt > bt) and (ve > be)
    print(f'  {tag:6s} full {v:+.4f}(base {b:+.4f}) · train {vt:+.4f}({bt:+.4f}) · '
          f'test {ve:+.4f}({be:+.4f}) → {"후보승격" if ok else "기각"}')
    return ok, s


def deep(tag, s):
    """3분할 · 잭나이프 · 발동일."""
    n = len(s)
    t = n // 3
    folds = [s[:t], s[t:2 * t], s[2 * t:]]
    print(f'  [{tag}] 3분할')
    allok = True
    for i, f in enumerate(folds, 1):
        b, v = statistics.fmean(x[1] for x in f), statistics.fmean(x[2] for x in f)
        good = v > b
        allok &= good
        print(f'    fold{i} (n={len(f)}) base {b:+.4f} · var {v:+.4f} → '
              f'{"우위" if good else "열위"}')
    d = [x[2] - x[1] for x in s]
    m = statistics.fmean(d)
    lo = min(statistics.fmean(d[:i] + d[i + 1:]) for i in range(len(d)))
    hi = max(statistics.fmean(d[:i] + d[i + 1:]) for i in range(len(d)))
    act = sum(1 for x in s if abs(x[2] - x[1]) > 1e-9)
    print(f'    3분할 {"통과" if allok else "미통과"} · 잭나이프 차이 {m:+.4f} '
          f'[{lo:+.4f}, {hi:+.4f}] 부호유지 {"예" if lo > 0 else "아니오"} · 발동 {act}일')
    return allok and lo > 0


def main():
    px, name, dates = B.load_panel()
    di = {d: i for i, d in enumerate(dates)}
    fo, ins = B.load_flow()
    fo_last = max((d for c in fo for d in fo[c]), default='-')
    ins_last = max((d for c in ins for d in ins[c]), default='-')
    print(f'패널 {os.path.basename(B.PANEL)} · {dates[0]}~{dates[-1]} ({len(dates)}일)')
    print(f'수급 패널 최종일 — 외국인 {fo_last} · 기관 {ins_last} '
          f'(외국인 {len(fo)}종 · 기관 {len(ins)}종)\n')

    print('[iteration 1] Rule X2 재검정 — 완전한 외국인 수급 패널')
    ok2, s2 = report('X2', series(px, name, dates, di, fo, ins, sel_x2))
    p2 = deep('X2', s2)
    print(f'  → X2 최종: {"승격 가능" if (ok2 and p2) else "승격 불가(기각)"}\n')

    print('[iteration 2] 신규 distinct 축 — 외국인×기관 결합 수급')
    res = {}
    for tag, fn in (('XC1', sel_xc1), ('XC2', sel_xc2), ('XC3', sel_xc3)):
        ok, s = report(tag, series(px, name, dates, di, fo, ins, fn))
        res[tag] = (ok, s)
    for tag, (ok, s) in res.items():
        if ok:
            deep(tag, s)


if __name__ == '__main__':
    main()
