import json, statistics, collections, bisect, os, sys
from bt_actually import load_px, sector_excess, BENCH
import themes
px, names = load_px()
dates, exc = sector_excess(px, names)
tset = sorted(exc)
def nt(d):
    i = bisect.bisect_left(tset, d); return tset[i] if i < len(tset) else None
rows = [json.loads(L) for L in open('actually2.jsonl', encoding='utf-8')]
# 그 거래일에 배정된 '반박 총 건수'(테마 매핑 여부 무관)
per = collections.Counter()
for r in rows:
    d = nt(r['date'])
    if d: per[d] += 1
# 벤치(KODEX200) 당일→익일 수익률
di = {d: i for i, d in enumerate(tset)}
bm = {}
for i, d in enumerate(tset[:-1]):
    a, b = px[BENCH].get(d), px[BENCH].get(tset[i+1])
    if a and b: bm[d] = (b/a-1)*100
days = [d for d in tset if d in bm]
def t_(v): return statistics.mean(v)/(statistics.stdev(v)/len(v)**.5) if len(v)>2 else float('nan')
print("■ 그날 반박 건수별 KODEX200 익일 수익률 (%) — '반박이 몰리는 날'의 성격")
g = collections.defaultdict(list)
for d in days: g[min(per.get(d,0),6)].append(bm[d])
for k in sorted(g):
    lbl=f"{k}건"+("+" if k==6 else "")
    print(f"  {lbl:<5} n={len(g[k]):>5}  KODEX200 익일 {statistics.mean(g[k]):+.4f}%  t={t_(g[k]):+.2f}")
allb=[bm[d] for d in days]
print(f"  전체 n={len(allb)}  평균 {statistics.mean(allb):+.4f}%")
