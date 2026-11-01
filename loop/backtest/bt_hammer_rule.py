# -*- coding: utf-8 -*-
"""2026-07-31 — 캔들 꼬리 신호를 [6-1] 단기 ETF 선정 규칙으로 검정.

`bt_hammer.py` 결과: 아래꼬리 비율은 익일 초과수익과 **음의** 상관(IC -0.039, t -4.55),
윗꼬리 비율은 **양의** 상관(+0.024, t +2.99). 통념과 반대다. 전일 수익률·종가위치를
통제해도 살아남았다(분위 내 IC -0.008 ~ -0.071).

여기서는 그 신호를 확정방법(mom20+RuleH) 위에 얹어 실제로 손익이 개선되는지 본다.
캔들점수 = 윗꼬리비율 - 아래꼬리비율 (클수록 유리하다는 가설).

1차 지표 = v2.3 P&L (픽5 동일가중 1일 회전 -10bp - KODEX200), %p/일.
가드: full·train·test 3개 모두 baseline 초과 → 3분할·잭나이프.
패널은 603거래일(`panel_ohlc_2y.csv`)로, 종전 루프(103일)보다 훨씬 길다.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_hammer as B  # noqa: E402

BENCH, COST = '069500', 0.0010


def mom(bar, c, d, di, dates, k):
    i = di[d]
    if i < k:
        return None
    a, b = bar[c].get(dates[i - k]), bar[c].get(d)
    return (b[3] / a[3] - 1.0) if (a and b) else None


def cand(bar, d, di, dates):
    out = []
    for c, v in bar.items():
        if d not in v:
            continue
        m = mom(bar, c, d, di, dates, 20)
        r1 = mom(bar, c, d, di, dates, 1)
        r3 = mom(bar, c, d, di, dates, 3)
        if m is None or r1 is None or r3 is None:
            continue
        if r1 > 0.10 or r3 > 0.20:                 # Rule H
            continue
        s = B.shape(v[d])
        if s is None:
            continue
        out.append({'code': c, 'mom': m, 'score': s['up_r'] - s['lo_r'],
                    'lo_r': s['lo_r']})
    return out


def base_sel(cs, **_):
    return [x['code'] for x in sorted(cs, key=lambda x: -x['mom'])[:5]]


def cs_rank(cs, pool=15, **_):
    """H1 — mom20 상위 pool 안에서 캔들점수 상위 5."""
    top = sorted(cs, key=lambda x: -x['mom'])[:pool]
    if len(top) < 5:
        return base_sel(cs)
    return [x['code'] for x in sorted(top, key=lambda x: -x['score'])[:5]]


def cs_drop(cs, cut=0.50, **_):
    """H2 — 아래꼬리 비율이 cut 초과인 종목을 제외하고 mom20 상위 5(차순위 충원)."""
    keep = [x for x in cs if x['lo_r'] <= cut]
    if len(keep) < 5:
        keep = cs
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]


def cs_blend(cs, pool=20, w=0.5, **_):
    """H3 — mom20 순위와 캔들점수 순위의 가중 블렌드."""
    top = sorted(cs, key=lambda x: -x['mom'])[:pool]
    if len(top) < 5:
        return base_sel(cs)
    r1 = {x['code']: i for i, x in enumerate(top)}
    r2 = {x['code']: i for i, x in enumerate(sorted(top, key=lambda x: -x['score']))}
    order = sorted(r1, key=lambda c: w * r2[c] + (1 - w) * r1[c])
    return order[:5]


def run(fn, bar, dates, di, **kw):
    out = []
    for i in range(21, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        cs = cand(bar, d, di, dates)
        if len(cs) < 20:
            continue
        picks = fn(cs, **kw)
        rets = [bar[c][nxt][3] / bar[c][d][3] - 1.0 for c in picks
                if bar[c].get(d) and bar[c].get(nxt)]
        ba, bb = bar[BENCH].get(d), bar[BENCH].get(nxt)
        if not rets or not (ba and bb):
            continue
        out.append((d, 100 * ((sum(rets) / len(rets) - COST) - (bb[3] / ba[3] - 1.0))))
    return out


def folds(v, k=3):
    n = len(v)
    return [v[i * n // k:(i + 1) * n // k] for i in range(k)]


def main():
    bar, nm, dates = B.load()
    di = {d: i for i, d in enumerate(dates)}
    variants = [
        ('baseline mom20+RuleH', base_sel, {}),
        ('H1 top15 → 캔들점수 top5', cs_rank, {'pool': 15}),
        ('H1b top25 → 캔들점수 top5', cs_rank, {'pool': 25}),
        ('H2 아래꼬리>0.50 제외', cs_drop, {'cut': 0.50}),
        ('H2b 아래꼬리>0.35 제외', cs_drop, {'cut': 0.35}),
        ('H3 랭크블렌드 w=0.5', cs_blend, {'w': 0.5}),
        ('H3b 랭크블렌드 w=0.3', cs_blend, {'w': 0.3}),
    ]
    print(f'패널 {len(bar)}종 · {len(dates)}거래일 ({dates[0]}~{dates[-1]})')
    print(f'\n{"변형":30s}{"전체":>9s}{"train":>9s}{"test":>9s}  판정')
    print('-' * 72)
    store, base = {}, None
    for lab, fn, kw in variants:
        r = run(fn, bar, dates, di, **kw)
        store[lab] = r
        v = [x[1] for x in r]
        h = len(v) // 2
        full, tr, te = statistics.fmean(v), statistics.fmean(v[:h]), statistics.fmean(v[h:])
        if base is None:
            base, verdict = (full, tr, te), f'기준선 (n={len(v)}일)'
        else:
            verdict = ('후보승격' if (full > base[0] and tr > base[1] and te > base[2])
                       else '기각(가드 미통과)')
        print(f'{lab:30s}{full:+9.4f}{tr:+9.4f}{te:+9.4f}  {verdict}')

    b = [x[1] for x in store['baseline mom20+RuleH']]
    print('\n=== 3분할·잭나이프 (1차 가드 통과분만) ===')
    for lab, _, _ in variants[1:]:
        v = [x[1] for x in store[lab]]
        h = len(v) // 2
        if not (statistics.fmean(v) > base[0] and statistics.fmean(v[:h]) > base[1]
                and statistics.fmean(v[h:]) > base[2]):
            continue
        ok = all(statistics.fmean(y) > statistics.fmean(x)
                 for x, y in zip(folds(b), folds(v)))
        diff = [q - p for p, q in zip(b, v)]
        jk = [statistics.fmean(diff[:i] + diff[i + 1:]) for i in range(len(diff))]
        print(f'{lab:30s} 3분할 {"통과" if ok else "미통과"} · 잭나이프하한 {min(jk):+.4f}')
        for i, (x, y) in enumerate(zip(folds(b), folds(v)), 1):
            print(f'    fold{i} {statistics.fmean(x):+.4f} → {statistics.fmean(y):+.4f}')


if __name__ == '__main__':
    main()
