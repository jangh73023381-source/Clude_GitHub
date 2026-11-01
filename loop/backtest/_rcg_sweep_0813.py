# -*- coding: utf-8 -*-
"""Rule RCG λ·β윈도 고원 정밀 스윕 (2026-08-13 iteration 2 후속) — 조회 전용."""
import os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bt_iter2_3_20260729 as B
from bt_loop_20260806 import jackknife, tstat
from bt_loop_20260813 import rcg_sel
B.PANEL = os.path.join(HERE, 'panel_close_0812.csv'); B.MINP = 0

px, name, dates = B.load_panel()
di = {d: i for i, d in enumerate(dates)}
fo, ins = B.load_flow()
base = B.run(B.base_sel, px, name, dates, di, fo, ins)
h = len(base)//2
bf, bt_, be = statistics.mean(base), statistics.mean(base[:h]), statistics.mean(base[h:])
print(f'baseline n={len(base)} full {bf:+.4f} train {bt_:+.4f} test {be:+.4f}')
print(f"{'w':>4s} {'lam':>5s} {'full':>8s} {'train':>8s} {'test':>8s} {'jk':>8s} {'t':>6s}  판정")
for w in (40, 60, 90):
    for lam in (0.0, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0, 3.0):
        r = B.run(rcg_sel, px, name, dates, di, fo, ins, lam=lam, w=w)
        if len(r) != len(base):
            print(f'{w:4d} {lam:5.2f}  표본 불일치 {len(r)}'); continue
        hh = len(r)//2
        f, tr, te = statistics.mean(r), statistics.mean(r[:hh]), statistics.mean(r[hh:])
        ok = f > bf and tr > bt_ and te > be
        jk = jackknife(r) if ok else None
        t = tstat(r, base)
        js = f'{jk:+8.4f}' if jk is not None else f'{"—":>8s}'
        v = 'PASS' if (jk is not None and jk > bf) else ('가드만' if ok else '미통과')
        print(f'{w:4d} {lam:5.2f} {f:+8.4f} {tr:+8.4f} {te:+8.4f} {js} {t:+6.2f}  {v}')
