"""신호 1·2·3개 조합 전수 검정. 20거래일 보유·리밸런싱, 시작 오프셋 0/5/10/15.
방법 RA = 적격 종목 내 순위 평균 상위 20% / AND = 각 신호 상위 30% 교집합(5종 미만이면 그 회차 제외).
기준선 = 같은 날 '그 조합의 모든 신호가 있는' 유동 종목 동일가중. 앞(~2023-06)/뒤(2023-07~) 분리."""
import numpy as np, pandas as pd, pickle, itertools
from gh_stats import nw_se
P = pickle.load(open('combo_sig.pkl', 'rb')); S, LIQ, start = P['S'], P['LIQ'], P['start']
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); C = Z['C']; bench = Z['bench']; T, N = C.shape
names = list(S); HZ = 20; SPLIT = 20230630
F = np.vstack([C[HZ:] / C[:-HZ] - 1, np.full((HZ, N), np.nan)]) * 100
KX = np.r_[(bench[HZ:] / bench[:-HZ] - 1) * 100, np.full(HZ, np.nan)]
RB = {off: list(range(start + off, T - HZ, HZ)) for off in (0, 5, 10, 15)}
allt = sorted({t for v in RB.values() for t in v})
def evaluate(combo, method):
    out = {}
    for t in allt:
        el = LIQ[t] & np.isfinite(F[t])
        for k in combo: el &= np.isfinite(S[k][t])
        idx = np.where(el)[0]
        if len(idx) < 100: continue
        R = np.column_stack([pd.Series(S[k][t, idx]).rank(pct=True).values for k in combo])
        if method == 'RA':
            sc = R.mean(1); sel = sc >= np.quantile(sc, .8)
        else:
            sel = (R >= .7).all(1)
            if sel.sum() < 5: continue
        r = F[t, idx]
        out[t] = (r[sel].mean() - r.mean(), r[sel].mean() - KX[t], sel.sum())
    return out
def stats(out, ts):
    x = np.array([out[t][0] for t in ts if t in out]); k = np.array([out[t][1] for t in ts if t in out])
    if len(x) < 10: return dict(n=len(x))
    n = len(x); k3 = n // 3; sr = np.sort(x)[::-1]
    return dict(n=n, ex=x.mean(), t=x.mean() / nw_se(x, 0), med=np.median(x), f1=x[:k3].mean(), f2=x[k3:2*k3].mean(), f3=x[2*k3:].mean(),
                r5=sr[max(3, int(n * .05)):].mean(), kodex=k.mean())
rows = []; raw = {}
combos = [(k,) for k in names] + list(itertools.combinations(names, 2)) + list(itertools.combinations(names, 3))
for i, cb in enumerate(combos):
    for m in (('RA',) if len(cb) == 1 else ('RA', 'AND')):
        o = evaluate(cb, m); raw[(cb, m)] = o
        r0 = RB[0]
        tr = [t for t in r0 if dates[t] <= SPLIT]; te = [t for t in r0 if dates[t] > SPLIT]
        a = stats(o, r0); b = stats(o, tr); c = stats(o, te)
        offs = [np.mean([o[t][0] for t in RB[off] if t in o]) for off in RB]
        rows.append(dict(조합=' + '.join(cb), k=len(cb), 방법=m, 종목수=np.mean([v[2] for v in o.values()]) if o else 0,
                         **{f'전체_{q}': a.get(q) for q in ('n', 'ex', 't', 'med', 'f1', 'f2', 'f3', 'r5', 'kodex')},
                         앞_ex=b.get('ex'), 앞_t=b.get('t'), 뒤_ex=c.get('ex'), 뒤_t=c.get('t'), 뒤_kodex=c.get('kodex'),
                         오프셋최소=min(offs), 오프셋평균=np.mean(offs)))
    if i % 40 == 0: print(i, len(combos), flush=True)
pd.DataFrame(rows).to_csv('combo_results.csv', index=False)
pickle.dump(raw, open('combo_raw.pkl', 'wb'))
print('done', len(rows))
