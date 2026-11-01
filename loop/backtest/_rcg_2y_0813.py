# -*- coding: utf-8 -*-
"""RCG·NL 을 2년 패널(602일)에서 재검정 — 고립 여부 확인. 조회 전용."""
import csv, os, statistics, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bt_iter2_3_20260729 as B
from bt_loop_20260806 import jackknife, tstat
from bt_loop_20260813 import rcg_sel
from _rcg_decomp_0813 import nl_sel
B.MINP = 0

def load2y():
    px, name = defaultdict(dict), {}
    for r in csv.DictReader(open(os.path.join(HERE,'panel_ohlc_2y.csv'), encoding='utf-8')):
        try: px[r['code']][r['date']] = float(r['close'])
        except (ValueError, KeyError): continue
        name[r['code']] = r['name']
    return px, name, sorted({d for c in px for d in px[c]})

px, name, dates = load2y()
di = {d: i for i, d in enumerate(dates)}
fo, ins = B.load_flow()
base = B.run(B.base_sel, px, name, dates, di, fo, ins)
h = len(base)//2
bf, bt_, be = statistics.mean(base), statistics.mean(base[:h]), statistics.mean(base[h:])
print(f'2년 패널 {len(dates)}일 ({dates[0]}~{dates[-1]}) · 코드 {len(px)}종')
print(f'baseline           full {bf:+.4f} train {bt_:+.4f} test {be:+.4f}  (n={len(base)})')
def show(lab, **kw):
    fn = kw.pop('fn')
    r = B.run(fn, px, name, dates, di, fo, ins, **kw)
    if len(r) != len(base):
        print(f'{lab:22s} 표본 불일치 {len(r)} vs {len(base)}'); return
    hh = len(r)//2
    f, tr, te = statistics.mean(r), statistics.mean(r[:hh]), statistics.mean(r[hh:])
    ok = f>bf and tr>bt_ and te>be
    jk = jackknife(r) if ok else None
    t = tstat(r, base)
    print(f'{lab:22s} full {f:+.4f} train {tr:+.4f} test {te:+.4f} '
          f'jk {("%+.4f"%jk) if jk is not None else "—":>8s} t {("%+.2f"%t) if t is not None else "—":>6s}'
          f'  {"PASS" if (jk is not None and jk>bf) else ("가드만" if ok else "미통과")}')
show('NL w60', fn=nl_sel, w=60)
show('NL w40', fn=nl_sel, w=40)
for lam in (0.25, 0.5, 0.75, 1.0, 1.5, 3.0):
    show(f'RCG w60 λ{lam}', fn=rcg_sel, lam=lam, w=60)
for lam in (0.25, 0.75):
    show(f'RCG w40 λ{lam}', fn=rcg_sel, lam=lam, w=40)
