#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_dup2_20260903.py — Rule DUP 정밀 검정 R2·R3·R4·R5. 캐시(_dup_cache.pkl) 사용."""
import os, pickle, random, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt_dup_20260903 as D
NPICK = 5

Z = pickle.load(open(os.path.join(HERE, '_dup_cache.pkl'), 'rb'))
cache, bidx, names = Z['cache'], Z['bidx'], Z['names']
imap = {c: D.norm(g, 1) for c, g in bidx.items()}


def dedup(order, cap, level, imap):
    """선정 순서를 훑되 정규화 기초지수당 최대 cap 종만 담고 차순위로 채운다.
       5종 미달 시 제약을 풀어 보충한다(관망하지 않는다). bt_dup_20260903.main 과 동일 구현."""
    from collections import defaultdict
    picks, cnt, skipped = [], defaultdict(int), []
    for c in order:
        if len(picks) >= NPICK:
            break
        g = imap.get(c)
        if g is not None and cnt[g] >= cap:
            skipped.append(c)
            continue
        picks.append(c)
        if g is not None:
            cnt[g] += 1
    for c in skipped + order:
        if len(picks) >= NPICK:
            break
        if c not in picks:
            picks.append(c)
    return picks[:NPICK]


def series(cap, im):
    out, act = [], 0
    for d, order, fw, bm in cache:
        base = order[:NPICK]
        picks = dedup(order, cap, 1, im) if cap else base
        rs = [fw.get(c) for c in picks]
        rs = [x for x in rs if x is not None]
        if len(rs) < NPICK:
            continue
        out.append((d, sum(rs) / len(rs) - bm))
        if cap and set(picks) != set(base):
            act += 1
    return out, act


b, _ = series(None, imap)
bmap = dict(b)
v, nact = series(1, imap)
dif = [(d, x - bmap[d]) for d, x in v if d in bmap]
dv = [x for _, x in dif]
n = len(dv)
print('=' * 74)
print('Rule DUP 정밀검정 — LV 기준선 x N1 cap1 · 7년 패널')
print('=' * 74)
print('  발동 %d일 / %d일 (%.1f%%) · D평균 %+.4f%%p · t %+.2f · 중앙값 %+.4f%%p'
      % (nact, n, nact / n * 100, statistics.mean(dv), D.tstat(dv), statistics.median(dv)))
nz = [x for x in dv if abs(x) > 1e-12]
print('  픽이 바뀐 날만: %d일 · 평균 %+.4f%%p · t %+.2f · 승 %d/%d (%.1f%%)'
      % (len(nz), statistics.mean(nz), D.tstat(nz), sum(1 for x in nz if x > 0),
         len(nz), sum(1 for x in nz if x > 0) / len(nz) * 100))

print('\n[R2] 3분할 fold')
k = n // 3
for fi, seg in enumerate((dv[:k], dv[k:2 * k], dv[2 * k:]), 1):
    print('   fold%d  D평균 %+.4f%%p  t%+.2f  %s'
          % (fi, statistics.mean(seg), D.tstat(seg),
             'PASS' if statistics.mean(seg) > 0 else '**FAIL**'))

print('\n[R5] 꼬리 기여도 (상위3일 제거 시 부호 반전이면 기각)')
s = sorted(dv, reverse=True)
tot = sum(s)
for k2 in (1, 3, 5, 10):
    print('   상위%2d일 제거 -> D평균 %+.4f%%p (상위%d일 기여 %.1f%%)'
          % (k2, statistics.mean(s[k2:]), k2, sum(s[:k2]) / tot * 100 if tot else 0))
w = sorted(dv)
print('   윈저화(5~95%%) 평균 %+.4f%%p'
      % statistics.mean(w[int(n * 0.05):int(n * 0.95)]))

print('\n[R4] 플라시보 — 기초지수 라벨 셔플 300회')
codes = sorted(set(imap) & {c for _, o, _, _ in cache for c in o})
labels = [imap[c] for c in codes]
rng = random.Random(20260903)
obs = statistics.mean(dv)
null = []
for _ in range(300):
    sh = labels[:]
    rng.shuffle(sh)
    v2, _a = series(1, dict(zip(codes, sh)))
    null.append(statistics.mean([x - bmap[d] for d, x in v2 if d in bmap]))
print('   관측 %+.4f%%p · 귀무평균 %+.4f%%p sd %.4f · 경험적 p = %.3f'
      % (obs, statistics.mean(null), statistics.stdev(null),
         sum(1 for x in null if x >= obs) / len(null)))

print('\n[R1 보강] 기준선 LV · 정규화 N1 · cap 격자')
for cap in (1, 2, 3, 4):
    vv, aa = series(cap, imap)
    dd = [x - bmap[d] for d, x in vv if d in bmap]
    print('   cap%d  발동%4d일  D평균 %+.4f%%p  t%+.2f  중앙값 %+.4f'
          % (cap, aa, statistics.mean(dd), D.tstat(dd), statistics.median(dd)))
