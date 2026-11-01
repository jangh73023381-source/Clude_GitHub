"""실적 발표일(장전 발표) 시가 갭 조건부 장중·사후 추종 검정. D0 시가 갭 = O[D0]/C[D-1]-1 (반도체 ETF). 갭이 크면 '시장이 서프라이즈로 읽음'.
진입 D0 시가 → D0 종가 / D+5 종가. 비교: 반도체 − KODEX200, 그리고 평범한 날 중 같은 크기 갭이 난 날."""
import numpy as np, pandas as pd
exec(open('earn_semis.py').read().split("# 리포트 목표가 수정")[0])
op = p.pivot(index='date', columns='code', values='open'); so, ko = op['091160'].values.astype(float), op['069500'].values.astype(float)
gap = (so / np.r_[np.nan, semi[:-1]] - 1) * 100
oc_s = (semi / so - 1) * 100; oc_k = (k200 / ko - 1) * 100
o5_s = (np.r_[semi[5:], [np.nan] * 5] / so - 1) * 100; o5_k = (np.r_[k200[5:], [np.nan] * 5] / ko - 1) * 100
allt = set()
for corp, s in E.items():
    t0s = [int(np.searchsorted(d, int(x))) for x in s.split() if d[0] <= int(x) <= d[-2]]; allt |= set(t0s)
    for lo, hi, nm in ((1.0, 99, '갭 ≥ +1%'), (0, 1.0, '갭 0~1%'), (-99, 0, '갭 < 0')):
        tt = [t for t in t0s if lo <= gap[t] < hi]
        if not tt: continue
        a = np.array([oc_s[t] - oc_k[t] for t in tt]); b = np.array([o5_s[t] - o5_k[t] for t in tt if np.isfinite(o5_s[t])])
        print(f'{corp} {nm}: n={len(tt)} 장중(시가→종가) 반도체 {np.nanmean([oc_s[t] for t in tt]):+.2f} 초과 {a.mean():+.2f} 양수 {(a>0).mean()*100:.0f}% | 시가→D+5 초과 {b.mean():+.2f} 양수 {(b>0).mean()*100:.0f}%')
# 평범한 날 같은 갭(≥+1%) 대조
norm = [t for t in range(1, len(d) - 6) if gap[t] >= 1.0 and all(abs(t - u) > 3 for u in allt)]
a = np.array([oc_s[t] - oc_k[t] for t in norm]); b = np.array([o5_s[t] - o5_k[t] for t in norm])
print(f'평범한 날 갭 ≥ +1%: n={len(norm)} 장중 초과 {np.nanmean(a):+.2f} 양수 {(a>0).mean()*100:.0f}% | D+5 초과 {np.nanmean(b):+.2f}')
print('오늘(10/28) 반도체 ETF 시가 갭은 패널 밖 — 하이닉스 9:05 +1.8%, 코스피 개장 +2.2%')
