import numpy as np, pandas as pd, pickle
exec(open('combo_run.py').read().split("rows = []; raw = {}")[0])
r = pd.read_csv('combo_results.csv')
sing = r[r.k == 1].set_index('조합')
train_pos = [k for k in names if sing.loc[k, '앞_t'] > 1.0]
print('앞절반 t>1 단일신호(사전선택):', train_pos)
cands = {'11개 전부 순위평균(사전 지정)': (tuple(names), 'RA'),
         '앞절반 양수 신호 순위평균': (tuple(train_pos), 'RA'),
         'NH+PVC (2개 최상위, 앞절반 5위)': (('NH 신고가근접', 'PVC 고가-거래량 상관↓'), 'RA'),
         'PVC+TT+OPG (3개 앞절반 5위)': (('PVC 고가-거래량 상관↓', 'TT 추세템플릿', 'OPG 영업이익성장'), 'RA'),
         'NH 단독(비교)': (('NH 신고가근접',), 'RA')}
# 7/30~7/31 극단일 포함 구간 식별
ext = [int(np.searchsorted(dates, d)) for d in (20260730, 20260731)]
rng = np.random.default_rng(11)
def detail(cb, m, pool=None):
    res = []
    for t in allt:
        el = LIQ[t] & np.isfinite(F[t])
        for k in cb: el &= np.isfinite(S[k][t])
        if pool is not None: el &= pool[t]
        idx = np.where(el)[0]
        if len(idx) < 60: continue
        R = np.column_stack([pd.Series(S[k][t, idx]).rank(pct=True).values for k in cb])
        sc = R.mean(1); sel = sc >= np.quantile(sc, .8); r_ = F[t, idx]
        rnd = [r_[rng.choice(len(idx), sel.sum(), replace=False)].mean() for _ in range(200)]
        res.append((t, r_[sel].mean() - r_.mean(), r_[sel].mean() - KX[t], r_.mean() - KX[t], np.mean(np.array(rnd) >= r_[sel].mean()),
                    any(t < e <= t + HZ for e in ext)))
    return pd.DataFrame(res, columns=['t', 'ex', 'kx', 'pool_kx', 'p_rand', 'has_ext'])
# 대형주 풀: 20일 거래대금 상위 200
cs_ = np.cumsum(np.nan_to_num(C * Z['V']), 0); v20 = np.full((T, N), np.nan); v20[20:] = (cs_[20:] - cs_[:-20]) / 20
BIG = np.zeros((T, N), bool)
for t in allt:
    v = np.where(LIQ[t], v20[t], -np.inf); BIG[t, np.argsort(-v)[:200]] = True
out = []
for nm, (cb, m) in cands.items():
    for pl, pool in (('유동 전체', None), ('대형 200', BIG)):
        d = detail(cb, m, pool); d0 = d[d.t.isin(RB[0])]
        tr = d0[dates[d0.t] <= SPLIT]; te = d0[dates[d0.t] > SPLIT]; x = d0.ex.values; n = len(x); k3 = n // 3
        sr = np.sort(x)[::-1]; nx = d0[~d0.has_ext]
        out.append(dict(후보=nm, 풀=pl, 신호수=len(cb), 회차=n, 초과=x.mean(), t=x.mean() / nw_se(x, 0), fold=f'{x[:k3].mean():.2f}/{x[k3:2*k3].mean():.2f}/{x[2*k3:].mean():.2f}',
                        R5_상위5pct제거=sr[max(3, int(n * .05)):].mean(), 앞=tr.ex.mean(), 뒤=te.ex.mean(), 무작위p중앙=d0.p_rand.median(),
                        KODEX대비=d0.kx.mean(), KODEX대비_731제외=nx.kx.mean(), 뒤_KODEX대비=te.kx.mean(), 풀자체_KODEX=d0.pool_kx.mean(),
                        오프셋4개_KODEX=d.kx.mean()))
o = pd.DataFrame(out); pd.set_option('display.width', 320); pd.set_option('display.max_columns', 30)
print(o.round(2).to_string(index=False)); o.to_csv('combo_final.csv', index=False)
