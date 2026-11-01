#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_base_long_20260819.py — 확정방법(baseline)을 **7년 패널(1,800일)** 에서 프로파일링.

왜 필요한가
  2년 패널(604일)은 KODEX200 누적 +206%의 **단일 강세장**이라 진짜 하락장이 없다
  (2026-08-14 세션 기록). `panel_ohlc_long.csv` 는 2019-04~2026-07 **1,800거래일**로
  2020 코로나 폭락과 2022 베어를 포함한다. **3배 표본 · 실제 하락장 포함.**
  2026-08-19 현재까지 이 자산은 한 번도 baseline 프로파일링에 쓰이지 않았다.

묻는 것
  ① baseline 의 KODEX200 대비 초과가 **하락장에서도 유지되는가** (저베타 구조의 값)
  ② 초과수익의 **꼬리 의존도(R5)** 가 2년에서 본 것과 같은가
  ③ **일평균 초과**와 **복리 누적·MDD** 가 같은 이야기를 하는가
     — 사용자는 매일 픽5를 전액 매수하므로 체감 지표는 복리와 MDD 다.
"""
import csv, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'references', 'scripts'))
from universe_filters import eligible                 # noqa: E402

LONG = os.path.join(HERE, 'panel_ohlc_long.csv')
BENCH, NPICK, MOM = '069500', 5, 20


def load():
    px, names = defaultdict(dict), {}
    r = csv.reader(open(LONG, encoding='utf-8'))
    h = next(r)
    ic, inm, idt, icl = h.index('code'), h.index('name'), h.index('date'), h.index('close')
    for row in r:
        try:
            px[row[ic]][row[idt]] = float(row[icl])
        except ValueError:
            continue
        names[row[ic]] = row[inm]
    return px, names


def build(px, names, dates):
    out = {}
    for i, d in enumerate(dates):
        if i < MOM:
            continue
        lst = []
        for c in px:
            if not eligible(names.get(c, '')):
                continue
            a, b = px[c].get(dates[i - MOM]), px[c].get(d)
            if not (a and b):
                continue
            c1, c3 = px[c].get(dates[i - 1]), px[c].get(dates[i - 3])
            if c1 and c3 and ((b / c1 - 1) * 100 > 10 or (b / c3 - 1) * 100 > 20):
                continue
            lst.append(((b / a - 1) * 100, c))
        lst.sort(reverse=True)
        out[d] = lst
    return out


def fwd(px, c, d, n):
    a, b = px[c].get(d), px[c].get(n)
    return None if not (a and b) else (b / a - 1) * 100


def cum(rs):
    x, o = 1.0, []
    for r in rs:
        x *= (1 + r / 100)
        o.append(x)
    return o


def mdd(cv):
    pk, w = cv[0], 0.0
    for x in cv:
        pk = max(pk, x)
        w = min(w, x / pk - 1)
    return w * 100


def main():
    px, names = load()
    dates = sorted({d for c in px for d in px[c]})
    cands = build(px, names, dates)
    rows = []
    for i, d in enumerate(dates[:-1]):
        n = dates[i + 1]
        bm = fwd(px, BENCH, d, n)
        cd = cands.get(d)
        if bm is None or not cd or len(cd) < NPICK:
            continue
        rs = [fwd(px, c, d, n) for _, c in cd[:NPICK]]
        rs = [x for x in rs if x is not None]
        if len(rs) < NPICK:
            continue
        rows.append((d, sum(rs) / len(rs), bm))

    N = len(rows)
    pick = [p for _, p, _ in rows]
    bench = [b for _, _, b in rows]
    ex = [p - b for p, b in zip(pick, bench)]
    cp, cb = cum(pick), cum(bench)
    yrs = N / 252
    print(f'=== baseline(mom20+RuleH) 7년 패널 · 채점 {N}일 ({rows[0][0]}~{rows[-1][0]}) ===\n')
    print(f'[절대] 픽5 누적 {(cp[-1]-1)*100:+.1f}% (연율 {(cp[-1]**(1/yrs)-1)*100:+.1f}%) '
          f'MDD {mdd(cp):.1f}% 일변동성 {statistics.stdev(pick):.2f}% '
          f'Sharpe(일) {statistics.mean(pick)/statistics.stdev(pick)*252**0.5:.2f}')
    print(f'[벤치] KODEX200 누적 {(cb[-1]-1)*100:+.1f}% (연율 {(cb[-1]**(1/yrs)-1)*100:+.1f}%) '
          f'MDD {mdd(cb):.1f}% 일변동성 {statistics.stdev(bench):.2f}% '
          f'Sharpe(일) {statistics.mean(bench)/statistics.stdev(bench)*252**0.5:.2f}')
    print(f'[초과] 평균 {statistics.mean(ex):+.4f}%p/일 · 승률 {sum(1 for x in ex if x>0)/N*100:.1f}% '
          f'· sd {statistics.stdev(ex):.2f} · t {statistics.mean(ex)/(statistics.stdev(ex)/N**0.5):+.2f}')
    print(f'[누적비] 픽5/벤치 {cp[-1]/cb[-1]:.3f}')

    print('\n=== R5 꼬리 의존도 (초과수익) ===')
    s = sorted(ex, reverse=True)
    tot = sum(s)
    print(f'  평균 {tot/N:+.4f} · 중앙값 {statistics.median(ex):+.4f}')
    for k in (1, 3, 5, 10, 20, 40):
        print(f'  상위 {k:2d}일 제거 → {(tot-sum(s[:k]))/(N-k):+.4f} ({sum(s[:k])/tot*100:6.1f}%)'
              f'   |   하위 {k:2d}일 제거 → {(tot-sum(s[-k:]))/(N-k):+.4f}')
    import numpy as np
    a = np.array(ex)
    for t in (0.01, 0.02, 0.05):
        lo, hi = np.quantile(a, [t, 1 - t])
        print(f'  윈저화 {int(t*100)}% 평균 {np.clip(a, lo, hi).mean():+.4f}')

    print('\n=== 연도별 — 하락장에서도 유지되는가 ===')
    print(f'  {"연도":6s} {"일수":>4s} {"픽5":>9s} {"벤치":>9s} {"초과평균":>9s} {"승률":>6s} {"픽MDD":>8s} {"벤MDD":>8s}')
    yb = defaultdict(list)
    for d, p, b in rows:
        yb[d[:4]].append((p, b))
    for y in sorted(yb):
        v = yb[y]
        pp, bb = cum([x for x, _ in v]), cum([z for _, z in v])
        e = [x - z for x, z in v]
        print(f'  {y:6s} {len(v):4d} {(pp[-1]-1)*100:+8.1f}% {(bb[-1]-1)*100:+8.1f}% '
              f'{statistics.mean(e):+8.4f} {sum(1 for x in e if x>0)/len(e)*100:5.1f}% '
              f'{mdd(pp):7.1f}% {mdd(bb):7.1f}%')

    print('\n=== 벤치 수익률 5분위별 초과 (저베타 구조 확인) ===')
    srt = sorted(rows, key=lambda r: r[2])
    q = N // 5
    for i in range(5):
        seg = srt[i * q:(i + 1) * q] if i < 4 else srt[4 * q:]
        e = [p - b for _, p, b in seg]
        bm = [b for _, _, b in seg]
        print(f'  Q{i+1} 벤치 {statistics.mean(bm):+6.2f}% → 초과 {statistics.mean(e):+7.4f}%p '
              f'(승률 {sum(1 for x in e if x>0)/len(e)*100:4.1f}%)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
