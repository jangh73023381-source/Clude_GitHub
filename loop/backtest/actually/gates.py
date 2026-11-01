import json, os, sys, statistics, random, collections, csv, bisect
from bt_actually import load_px, sector_excess, BENCH
import themes

px, names = load_px()
dates, exc = sector_excess(px, names)
tset = sorted(exc)
base = collections.defaultdict(list)
for d in tset:
    for s, v in exc[d].items(): base[s].append(v)
smean = {s: statistics.mean(v) for s, v in base.items()}
SECS = sorted(smean)
def nt(d):
    i = bisect.bisect_left(tset, d); return tset[i] if i < len(tset) else None
def t_(v): return statistics.mean(v)/(statistics.stdev(v)/len(v)**.5) if len(v) > 2 else float('nan')

rows = [json.loads(L) for L in open('actually2.jsonl', encoding='utf-8')]
raw = []
for r in rows:
    t = themes.theme(r['title'] + ' ' + r['lead'])
    if not t: continue
    d = nt(r['date'])
    if d: raw.append((d, t))
cnt = collections.Counter(raw)

# ---- 지평 D+1 / D+2 / D+3 (2건 셀 vs 전체)
di = {d: i for i, d in enumerate(tset)}
def horizon(pairs, k):
    v = []
    for d, s in pairs:
        i = di.get(d)
        if i is None or i + k - 1 >= len(tset): continue
        dd = tset[i + k - 1]
        if s in exc.get(dd, {}): v.append(exc[dd][s] - smean[s])
    return v
allp = [(d, s) for d, s in raw if s in exc.get(d, {})]
two  = [(d, s) for d, s in allp if cnt[(d, s)] == 2]
print("■ 지평별 (섹터조정 %p)")
for lbl, P in [('전체 897', allp), ('2건셀 118', two)]:
    o = []
    for k in (1, 2, 3):
        v = horizon(P, k); o.append(f"D+{k} {statistics.mean(v):+.4f}(t={t_(v):+.2f})")
    print(f"  {lbl:<12} " + "  ".join(o))

# ---- R5 (2건 셀)
v2 = horizon(two, 1); s2 = sorted(v2)
print(f"\n■ R5 (2건 셀 n={len(v2)}) 평균 {statistics.mean(v2):+.4f} · 중앙 {statistics.median(v2):+.4f}"
      f" · 하위3제거 {statistics.mean(s2[3:]):+.4f} · 하위10제거 {statistics.mean(s2[10:]):+.4f}"
      f" · 승률 {sum(1 for x in v2 if x>0)/len(v2)*100:.1f}%")

# ---- ★ 매핑 셔플 대조군 200회
random.seed(20260908)
def shuffled_stat(P):
    ds = [d for d, _ in P]; ss = [s for _, s in P]
    random.shuffle(ss)
    v = [exc[d][s] - smean[s] for d, s in zip(ds, ss) if s in exc.get(d, {})]
    return statistics.mean(v) if v else 0.0
for lbl, P, obs in [('전체', allp, statistics.mean(horizon(allp, 1))),
                    ('2건셀', two, statistics.mean(v2))]:
    dd = sorted(shuffled_stat(P) for _ in range(200))
    p = sum(1 for x in dd if x <= obs) / len(dd)
    print(f"\n■ 매핑 셔플 대조군 200회 [{lbl}] 관측 {obs:+.4f} · 귀무 평균 {statistics.mean(dd):+.4f}"
          f" · sd {statistics.stdev(dd):.4f} · 최소 {dd[0]:+.4f} · 5%분위 {dd[10]:+.4f}")
    print(f"  ★ 경험적 p (관측 이하) = {p:.3f}")
