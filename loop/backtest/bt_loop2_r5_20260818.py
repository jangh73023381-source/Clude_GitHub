#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R5 — SRV 의 '실전 가능 경로' 검정.

KRX 업종지수는 D+1 공개라 선정 시각에 D 값을 못 받는다. 당일 확보 가능한 유일한 대체물은
**이미 매일 받는 ETF 종가**로 업종을 대용하는 것이다(같은 업종에 매핑된 ETF들의 등가중
수익률, 자기 자신 제외). 이 경로가 살아나는지, 아니면 2026-08-14 기각된 Rule THM
(테마 수준 모멘텀 집계)으로 수렴하는지를 가른다.
"""
import os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_breadth_20260818 as B
import bt_loop2_20260818 as L


def proxy_sector_ret(px, names, dates, c2s):
    """일자별 업종 대용 수익률(당일 D 종가로 계산 가능)."""
    bysec = defaultdict(list)
    for c, s in c2s.items():
        if s:
            bysec[s].append(c)
    out = {}
    for i, d in enumerate(dates):
        if i == 0:
            continue
        prev = dates[i - 1]
        row = {}
        for s, cs in bysec.items():
            rs = []
            for c in cs:
                a, b = px[c].get(prev), px[c].get(d)
                if a and b:
                    rs.append((b / a - 1) * 100)
            if len(rs) >= 2:
                row[s] = sum(rs) / len(rs)
        out[d] = row
    return out


def main():
    px, names = B.load_etf()
    brd = B.load_breadth()
    B.BRD_DATES = sorted(brd)
    dates = sorted({d for c in px for d in px[c]})
    dates = [d for d in dates if d >= B.BRD_DATES[0]]
    c2s = {c: L.etf_sector(names.get(c, '')) for c in px}
    prox = proxy_sector_ret(px, names, dates, c2s)
    real = L.load_sector_idx()

    # 상관 — 대용치가 실제 업종지수를 얼마나 따라가는가
    import statistics
    cors = []
    for s in {v for v in c2s.values() if v}:
        xs, ys = [], []
        for d in dates:
            a = prox.get(d, {}).get(s)
            b = real.get(d, {}).get(s)
            if a is not None and b is not None:
                xs.append(a); ys.append(b)
        if len(xs) > 30:
            mx, my = statistics.mean(xs), statistics.mean(ys)
            num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
            cors.append((num / den if den else 0, s, len(xs)))
    cors.sort(reverse=True)
    print('업종 대용(ETF 등가중) vs KRX 업종지수 일간수익률 상관')
    for r, s, n in cors:
        print(f'   {s:14s} r={r:+.3f} (n={n})')
    print(f'   중앙값 r={statistics.median(x[0] for x in cors):+.3f}\n')

    base = B.stat(B.run(B.sel_base, px, names, dates, brd), 'BASE')
    B.show(base)
    print()
    B.BRD_DATES = sorted(brd)
    # 대용치는 ETF 패널 일자 기준이므로 lag 를 직접 처리한다
    pdates = sorted(prox)

    def tilt(span, pool, lag):
        def f(cands, d, brd_):
            ds = [x for x in pdates if x <= d]
            if lag:
                ds = ds[:-lag] if len(ds) > lag else []
            ds = ds[-span:]
            if len(ds) < span:
                return B.sel_base(cands, d, brd_)
            sc = []
            for _, c in cands[:pool]:
                s = c2s.get(c)
                if not s:
                    continue
                vs = [prox[x].get(s) for x in ds]
                vs = [v for v in vs if v is not None]
                if vs:
                    sc.append((sum(vs), c))
            if len(sc) < B.NPICK:
                return B.sel_base(cands, d, brd_)
            sc.sort(reverse=True)
            return [c for _, c in sc[:B.NPICK]]
        return f

    for lag in (0, 1):
        tag = 'D(당일 확보 가능)' if lag == 0 else 'D-1'
        for span in (3, 5, 8):
            for pool in (10, 15):
                s = B.stat(B.run(tilt(span, pool, lag), px, names, dates, brd),
                           f'PRX 업종대용 {span}일/pool{pool} [{tag}]')
                B.show(s, base)
    return 0


if __name__ == '__main__':
    sys.exit(main())
