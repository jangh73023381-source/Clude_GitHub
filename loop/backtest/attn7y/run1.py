import json, statistics, pickle, os
from bt_attn import *
px, names = load_px()
dates = sorted({d for c in px for d in px[c]})
cands = build_cands(px, names, dates)
pickle.dump({'dates': dates, 'cands': cands}, open('_cache.pkl', 'wb'))
ser, cols = load_search('sector_search.csv')
sc = attn_scores(ser, 5, 20)
base = series(px, dates, cands, mk_picker('LV', None, sc))
mom  = series(px, dates, cands, mk_picker('MOM', None, sc))
print(f"패널 {len(dates)}일 {dates[0]}~{dates[-1]} · 선정일 {len(base)}")
print(f"baseline LV  평균 {statistics.mean([x[1] for x in base]):+.4f}%p/일  t={tstat([x[1] for x in base]):+.2f}")
print(f"참고     MOM 평균 {statistics.mean([x[1] for x in mom]):+.4f}%p/일  t={tstat([x[1] for x in mom]):+.2f}")
# 섹터 커버리지
covered = set(cols)
allsec = {}
for d, lst in list(cands.items())[::200]:
    for x in lst[:30]: allsec[x[3]] = allsec.get(x[3], 0) + 1
miss = {k: v for k, v in allsec.items() if k not in covered}
print("pool30 등장 섹터 중 키워드 없음:", sorted(miss.items(), key=lambda x: -x[1])[:8])
tot = sum(allsec.values()); cov = sum(v for k, v in allsec.items() if k in covered)
print(f"키워드 커버리지: {cov}/{tot} = {cov/tot*100:.1f}%")
json.dump({'base': base, 'mom': mom}, open('_base.json', 'w'))
