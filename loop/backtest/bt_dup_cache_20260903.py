#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_dup_cache_20260903.py — Rule DUP 검정용 선정순서 캐시 생성(1회).
   이 마운트의 셸은 호출이 끝나면 백그라운드 프로세스를 정리한다(2026-09-03 실측).
   무거운 캐시 생성과 반복 검정을 두 스크립트로 나눠 각각 셸 제한 안에서 완주시킨다."""
import os, pickle, statistics, sys, time
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_base_long_20260819 as L
import bt_dup_20260903 as D

t0 = time.time()
px, names = L.load()
dates = sorted({d for c in px for d in px[c]})
cands = L.build(px, names, dates)
print('build %.1fs' % (time.time() - t0), flush=True)

rets = defaultdict(dict)
for c in px:
    ds = sorted(px[c])
    for a, b in zip(ds, ds[1:]):
        x, y = px[c][a], px[c][b]
        if x and y:
            rets[c][b] = (y / x - 1) * 100


def sigma(c, i, k=20):
    v = [rets[c].get(dates[j]) for j in range(max(1, i - k + 1), i + 1)]
    v = [x for x in v if x is not None]
    return statistics.stdev(v) if len(v) >= max(5, k // 3) else None


cache = []
for i, d in enumerate(dates[:-1]):
    nxt = dates[i + 1]
    cd = cands.get(d)
    if not cd or len(cd) < L.NPICK:
        continue
    bm = rets[L.BENCH].get(nxt)
    if bm is None:
        continue
    sc = []
    for _, c in cd[:30]:
        s = sigma(c, i)
        if s is not None:
            sc.append((s, c))
    if len(sc) < L.NPICK:
        order = [c for _, c in cd][:40]
    else:
        sc.sort()
        seen = {x for _, x in sc}
        order = ([c for _, c in sc] + [c for _, c in cd if c not in seen])[:40]
    fw = {c: L.fwd(px, c, d, nxt) for c in order}
    cache.append((d, order, fw, bm))
print('cache %d days %.1fs' % (len(cache), time.time() - t0), flush=True)

bidx = D.load_baseidx()
out = os.path.join(HERE, '_dup_cache.pkl')
with open(out, 'wb') as f:
    pickle.dump({'cache': cache, 'bidx': bidx,
                 'codes': sorted(set(bidx) & set(px)),
                 'names': {c: names.get(c, '') for c in px}}, f)
print('saved %s %.1fs' % (out, time.time() - t0), flush=True)
