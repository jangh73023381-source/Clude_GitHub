#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rule USX 실전 집행 검정 — 룩어헤드 분해.

close(d)→close(d+1) 하네스는 **종가 d 매수**를 가정한다. 그런데 미국 날짜 d 세션은
종가 d **이후**(22:30~05:00 KST)에 열린다. 따라서 US_d 를 쓰면서 close(d) 에 사는 것은
불가능하다 — 실제 집행은 **open(d+1) 매수**다.

  A) close(d)→close(d+1) : 갭 포함 (룩어헤드)
  B) open(d+1)→close(d+1): 실제 집행 가능 구간
"""
import csv, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'references', 'scripts'))
from universe_filters import eligible  # noqa: E402
sys.path.insert(0, HERE)
from bt_usx_20260821 import theme_of, THEMES, MOM, NPICK, BENCH, LONG, US

CACHE = os.path.join(HERE, '_usx_exec_cache.json')


def build():
    px, op, names = defaultdict(dict), defaultdict(dict), {}
    r = csv.reader(open(LONG, encoding='utf-8')); h = next(r)
    ic, inm, idt, icl, iop = (h.index('code'), h.index('name'), h.index('date'),
                              h.index('close'), h.index('open'))
    for row in r:
        try:
            px[row[ic]][row[idt]] = float(row[icl]); op[row[ic]][row[idt]] = float(row[iop])
        except ValueError:
            continue
        names[row[ic]] = row[inm]
    dates = sorted({d for m in px.values() for d in m})
    cl = defaultdict(dict)
    r = csv.reader(open(US, encoding='utf-8')); next(r)
    for th, tk, d, c in r:
        cl[th][d] = float(c)
    usr = {}
    for th, m in cl.items():
        ds = sorted(m)
        usr[th] = [(ds[i], (m[ds[i]] / m[ds[i - 1]] - 1) * 100) for i in range(1, len(ds))]

    def us_at(th, d):
        arr = usr.get(th, []); lo, hi = 0, len(arr)
        while lo < hi:
            mid = (lo + hi) // 2
            if arr[mid][0] <= d:
                lo = mid + 1
            else:
                hi = mid
        return arr[lo - 1][1] if lo else None

    days = []
    for i in range(MOM, len(dates) - 1):
        d, n = dates[i], dates[i + 1]
        bc, bn, bo = px[BENCH].get(d), px[BENCH].get(n), op[BENCH].get(n)
        if not (bc and bn and bo):
            continue
        rows = []
        for c in px:
            nm = names.get(c, '')
            if not eligible(nm):
                continue
            a, b = px[c].get(dates[i - MOM]), px[c].get(d)
            if not (a and b):
                continue
            c1, c3 = px[c].get(dates[i - 1]), px[c].get(dates[i - 3])
            if c1 and c3 and ((b / c1 - 1) * 100 > 10 or (b / c3 - 1) * 100 > 20):
                continue
            nx, no = px[c].get(n), op[c].get(n)
            if not (nx and no):
                continue
            rows.append([(b / a - 1) * 100, theme_of(nm), (nx / b - 1) * 100,
                         (nx / no - 1) * 100, (no / b - 1) * 100])
        if len(rows) < NPICK:
            continue
        days.append({'d': d, 'bc': (bn / bc - 1) * 100, 'bo': (bn / bo - 1) * 100,
                     'bg': (bo / bc - 1) * 100, 'rows': rows,
                     'us': {th: us_at(th, d) for th in THEMES}})
    json.dump(days, open(CACHE, 'w'))
    return days


def load():
    return json.load(open(CACHE)) if os.path.exists(CACHE) else build()


def run(days, lam):
    A = B = G = 0.0
    n = 0
    for day in days:
        sc = []
        for mom, th, fcc, foc, fgap in day['rows']:
            s = mom
            if lam:
                u = day['us'].get(th)
                if u is not None:
                    s = mom + lam * u
            sc.append((s, fcc, foc, fgap))
        sc.sort(reverse=True)
        t = sc[:NPICK]
        A += sum(x[1] for x in t) / len(t) - day['bc']
        B += sum(x[2] for x in t) / len(t) - day['bo']
        G += sum(x[3] for x in t) / len(t) - day['bg']
        n += 1
    return A / n, B / n, G / n, n


if __name__ == '__main__':
    days = load()
    print(f'{"lam":>6} | {"A 종가→종가(룩어헤드)":>22} | {"B 시가→종가(집행가능)":>22} | {"G 갭구간":>12}')
    for lam in (0, 0.5, 1, 2, 5, 12, 50, 200):
        a, b, g, n = run(days, lam)
        print(f'{lam:>6} | {a:>+21.4f} | {b:>+21.4f} | {g:>+11.4f}   (n={n})')
