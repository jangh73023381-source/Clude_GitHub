# -*- coding: utf-8 -*-
"""EQLV 대조군 C3(무관 라벨 172/11/4, 200회) · pool30 주식 무작위5 (200회). seed 20260929."""
import sys; sys.path.insert(0, '/home/claude/w/test'); sys.path.insert(0, '/home/claude/w/test/eqlv')
from common import *
cls = pd.read_csv('/home/claude/w/debate/prereg_mom_classes.csv', dtype={'code': str})
cmap = dict(zip(cls.code, cls.cls))
isEq = np.array([cmap.get(c) == '주식' for c in codes])
S20 = E.vol(20); fOO = E.fOO
# 일자별 LV 순서(σ 유효 종목, 안정정렬) 사전계산 — 표본일 규칙은 perf.py 와 동일
days, ORD, POOL = [], {}, {}
for i in range(20, E.T - 3):
    pl = E.pool(i)
    if len(pl) < 5: continue
    v = S20[i, pl]; m = ~np.isnan(v)
    ORD[i] = pl[m][np.argsort(v[m], kind='stable')] if m.sum() >= 5 else None
    POOL[i] = pl; days.append(i)
def run_lab(lab):
    out = []
    for i in days:
        o = ORD[i]
        if o is None: pk = POOL[i][:5]
        else:
            eq = o[lab[o]][:5]
            pk = eq if len(eq) == 5 else np.concatenate([eq, o[~lab[o]][:5 - len(eq)]])
        if np.isnan(E.fA[i, pk]).any(): continue
        x = fOO[i, pk]; out.append(np.nanmean(x) if (~np.isnan(x)).any() else np.nan)
    return np.array(out)
act = run_lab(isEq); pa = prof(act)
print(f'EQLV OO 실제 Sh {pa["sharpe"]:.3f} MDD {pa["mdd"]:.1f}  (n={len(act)})')
rng = np.random.default_rng(20260929)
elig_idx = np.where(E.elig)[0]
shs, mdds = [], []
for r in range(200):
    lab = np.zeros(E.N, bool); perm = rng.permutation(elig_idx); lab[perm[:172]] = True
    p = prof(run_lab(lab)); shs.append(p['sharpe']); mdds.append(p['mdd'])
shs = np.array(shs); mdds = np.array(mdds)
print(f'C3 무관라벨: 귀무 Sh 평균 {shs.mean():.3f} (5~95% {np.quantile(shs,.05):.3f}~{np.quantile(shs,.95):.3f}) p(Sh≥실제)={(shs>=pa["sharpe"]).mean():.3f} | 귀무 MDD 평균 {mdds.mean():.1f} p(MDD≥실제)={(mdds>=pa["mdd"]).mean():.3f}')
# pool30 주식 무작위 5 (주식 5 미만이면 비주식 무작위로 채움)
shs, mdds = [], []
for r in range(200):
    out = []
    for i in days:
        pl = POOL[i]; eq = pl[isEq[pl]]; ne = pl[~isEq[pl]]
        if len(eq) >= 5: pk = rng.choice(eq, 5, replace=False)
        else: pk = np.concatenate([eq, rng.choice(ne, 5 - len(eq), replace=False)])
        if np.isnan(E.fA[i, pk]).any(): continue
        x = fOO[i, pk]; out.append(np.nanmean(x) if (~np.isnan(x)).any() else np.nan)
    p = prof(np.array(out)); shs.append(p['sharpe']); mdds.append(p['mdd'])
shs = np.array(shs); mdds = np.array(mdds)
print(f'pool30 주식 무작위5: 귀무 Sh 평균 {shs.mean():.3f} (95% {np.quantile(shs,.95):.3f}) p(Sh≥실제)={(shs>=pa["sharpe"]).mean():.3f} | 귀무 MDD 평균 {mdds.mean():.1f} (95% {np.quantile(mdds,.95):.1f}) p(MDD≥실제)={(mdds>=pa["mdd"]).mean():.3f}')
