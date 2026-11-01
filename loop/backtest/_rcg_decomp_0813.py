# -*- coding: utf-8 -*-
"""RCG 이득 분해 — 잔차조정(λ) 효과 vs 베타계산 가능 표본 제한 효과. 조회 전용."""
import os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bt_iter2_3_20260729 as B
from bt_loop_20260806 import jackknife, tstat
from bt_loop_20260813 import rcg_sel
import bt_loop_20260812 as P12
B.PANEL = os.path.join(HERE, 'panel_close_0812.csv'); B.MINP = 0

def hist_ok(px, c, d, di, dates, w):
    i = di[d]
    if i < w: return False
    n = sum(1 for j in range(i-w+1, i+1) if px[c].get(dates[j]))
    return n >= w*0.8

def nl_sel(cand, px=None, d=None, di=None, dates=None, w=60, **_):
    """Rule NL — 가격 이력 w일 이상인 종목만으로 mom20 상위 5종 (λ=0 등가)."""
    keep = [x for x in cand if hist_ok(px, x['code'], d, di, dates, w)]
    if len(keep) < 5: return B.base_sel(cand)
    return [x['code'] for x in sorted(keep, key=lambda x: -x['mom'])[:5]]

px, name, dates = B.load_panel()
di = {d: i for i, d in enumerate(dates)}
fo, ins = B.load_flow()
base = B.run(B.base_sel, px, name, dates, di, fo, ins)
h = len(base)//2
bf, bt_, be = statistics.mean(base), statistics.mean(base[:h]), statistics.mean(base[h:])
print(f'baseline           full {bf:+.4f} train {bt_:+.4f} test {be:+.4f}  (n={len(base)})')
def show(lab, r):
    hh = len(r)//2
    f, tr, te = statistics.mean(r), statistics.mean(r[:hh]), statistics.mean(r[hh:])
    ok = f>bf and tr>bt_ and te>be
    jk = jackknife(r) if ok else None
    t = tstat(r, base)
    print(f'{lab:22s} full {f:+.4f} train {tr:+.4f} test {te:+.4f} '
          f'jk {("%+.4f"%jk) if jk is not None else "—":>8s} t {("%+.2f"%t) if t is not None else "—":>6s}')
    return r
for w in (40, 60):
    show(f'NL w{w} (λ=0 등가)', B.run(nl_sel, px, name, dates, di, fo, ins, w=w))
for lam in (0.25, 0.75, 1.5, 3.0):
    show(f'RCG w60 λ{lam}', B.run(rcg_sel, px, name, dates, di, fo, ins, lam=lam, w=60))
# 제외된 종목 수 확인
i = len(dates)-2
d = dates[i]
cand = B.build_cand(px, name, d, di, dates)
ex = [x['name'] for x in cand if not hist_ok(px, x['code'], d, di, dates, 60)]
print(f'\n{d} 후보 {len(cand)}종 중 이력<60일 제외 {len(ex)}종: {", ".join(ex[:12])}')
