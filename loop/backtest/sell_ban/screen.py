#!/usr/bin/env python3
"""1차 스크리닝 — 40 신호 × 금지기간 H(5·10·20·40). 결과 screen_results.csv (조회 전용)."""
import os, time
import numpy as np, pandas as pd
import engine as E, signals
t0 = time.time()
d = E.load(); I = E.indicators(d); S = signals.build(I); C = I['C']
N = C.shape[1]
pr = E.xrank(I['MOM20']); q = np.floor(np.clip(pr, 0, 0.9999) * 5)   # mom20 5분위(D 기준)
rows = []
for H in (5, 10, 20, 40):
    R, X = E.fwd(C, H)
    FE = np.nanmean(X, axis=1)
    XQ = np.full_like(R, np.nan)
    for t in range(N):
        r, qq = R[:, t], q[:, t]
        ok = ~np.isnan(r) & ~np.isnan(qq)
        for k in range(5):
            s = ok & (qq == k)
            if s.sum() >= 3:
                XQ[s, t] = r[s] - r[s].mean()
    valid = ~np.isnan(X)
    for name, sig in S.items():
        st = E.stats(sig, X, H, R=R, FE=FE, XQ=XQ, N=N)
        ban = pd.DataFrame(sig.T.astype(float)).rolling(H, min_periods=1).max().values.T > 0
        st.update(sig=name, H=H, cover=(ban & valid).sum() / valid.sum() * 100,
                  per_stock_yr=sig.sum() / valid.any(axis=1).sum() / (N / 250))
        rows.append(st)
    print('H', H, f'{time.time()-t0:.1f}s', flush=True)
df = pd.DataFrame(rows)
cols = ['sig', 'H', 'n', 'ndates', 'cover', 'raw', 'mean', 'med', 'neg', 'dmean', 'dmed', 't', 'f1', 'f2', 'f3',
        'r5_1', 'r5_3', 'r5_5', 'r5_10', 'fe', 'momq', 'per_stock_yr']
df[cols].to_csv(os.path.join(E.HERE, 'screen_results.csv'), index=False, encoding='utf-8-sig')
print('done', len(df), f'{time.time()-t0:.1f}s')
