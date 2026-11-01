"""microsoft/qlib Alpha158 특징(정의는 qlib/contrib/data/loader.py 그대로) — 개별주 횡단면 검정.
5거래일 간격 표본일, 유동 종목 내 순위. 방향은 앞 절반 IC 부호로 정하고 뒤 절반에서 확인(사후 선택 방지).
지표: 상위 10% − 유동 평균, 5일·20일 보유. vwap 없음 → (H+L+C)/3."""
import numpy as np, pandas as pd, pickle
from gh_stats import nw_se
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); O, H, L, C, V = (Z[k] for k in 'OHLCV'); T, N = C.shape
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
D = lambda A: pd.DataFrame(A)
ref = lambda A, d: np.vstack([np.full((d, N), np.nan), A[:-d]])
F5 = np.vstack([C[5:] / C[:-5] - 1, np.full((5, N), np.nan)]) * 100
F20 = np.vstack([C[20:] / C[:-20] - 1, np.full((20, N), np.nan)]) * 100
SPLIT = 20230630
ts = list(range(260, T - 20, 5))
def run(X):
    out = {5: [], 20: []}; ic = []
    for t in ts:
        m = LIQ[t] & np.isfinite(X[t]) & np.isfinite(F20[t])
        if m.sum() < 200: continue
        x = X[t, m]
        if np.unique(x).size < 20: continue
        q = x >= np.quantile(x, .9); qb = x <= np.quantile(x, .1)
        for h, FF in ((5, F5), (20, F20)):
            r = FF[t, m]; out[h].append((t, r[q].mean() - r.mean(), r[qb].mean() - r.mean()))
        ic.append((t, pd.Series(x).corr(pd.Series(F20[t, m]), method='spearman')))
    return out, ic
rows = []
class _E(dict):
    def __setitem__(self, k, X):
        ev(k, X)
def ev(k, X):
    out, ic = run(X)
    if len(ic) < 100: return
    icd = pd.DataFrame(ic, columns=['t', 'ic']); tr = icd[dates[icd.t] <= SPLIT]; sign = 1 if tr.ic.mean() >= 0 else -1
    row = dict(특징=k, 방향=('높을수록' if sign > 0 else '낮을수록'), 앞_IC=tr.ic.mean(), 뒤_IC=icd[dates[icd.t] > SPLIT].ic.mean() * 1)
    for h in (5, 20):
        a = pd.DataFrame(out[h], columns=['t', 'top', 'bot']); a['x'] = a.top if sign > 0 else a.bot
        te = a[dates[a.t] > SPLIT].x.values; trx = a[dates[a.t] <= SPLIT].x.values; lag = h // 5 - 1
        row[f'앞_{h}일'] = trx.mean(); row[f'뒤_{h}일'] = te.mean(); row[f'뒤_{h}일_t'] = te.mean() / nw_se(te, lag)
        if h == 20:
            sr = np.sort(te)[::-1]; row['뒤_20일_상위5%제거'] = sr[max(2, int(len(te) * .05)):].mean()
    rows.append(row)
F = _E()
with np.errstate(invalid='ignore', divide='ignore'):
    e = 1e-12
    F['KMID'] = (C - O) / O; F['KLEN'] = (H - L) / O; F['KMID2'] = (C - O) / (H - L + e)
    F['KUP'] = (H - np.fmax(O, C)) / O; F['KUP2'] = (H - np.fmax(O, C)) / (H - L + e)
    F['KLOW'] = (np.fmin(O, C) - L) / O; F['KLOW2'] = (np.fmin(O, C) - L) / (H - L + e)
    F['KSFT'] = (2 * C - H - L) / O; F['KSFT2'] = (2 * C - H - L) / (H - L + e)
    dC = C - ref(C, 1); up = (dC > 0).astype(float); dn = (dC < 0).astype(float)
    up[np.isnan(dC)] = np.nan; dn[np.isnan(dC)] = np.nan
    ret = C / ref(C, 1); lv = np.log(V + 1); lvr = np.log(V / ref(V, 1) + 1)
    dV = V - ref(V, 1)
    tidx = None
    for d in (5, 10, 20, 30, 60):
        rc, rh, rl, rv = D(C).rolling(d), D(H).rolling(d), D(L).rolling(d), D(V).rolling(d)
        F[f'ROC{d}'] = ref(C, d) / C
        F[f'MA{d}'] = rc.mean().values / C
        F[f'STD{d}'] = rc.std().values / C
        t = np.arange(T, dtype=float)[:, None] * np.ones((1, N))
        cov = D(C).rolling(d).cov(D(t)).values if False else None
        mx = rh.max().values; mn = rl.min().values
        F[f'MAX{d}'] = mx / C; F[f'MIN{d}'] = mn / C
        F[f'QTLU{d}'] = rc.quantile(.8).values / C; F[f'QTLD{d}'] = rc.quantile(.2).values / C
        F[f'RSV{d}'] = (C - mn) / (mx - mn + e)
        F[f'CORR{d}'] = D(C).rolling(d).corr(D(lv)).values
        F[f'CORD{d}'] = D(ret).rolling(d).corr(D(lvr)).values
        cp = D(up).rolling(d).mean().values; cn = D(dn).rolling(d).mean().values
        F[f'CNTP{d}'] = cp; F[f'CNTN{d}'] = cn; F[f'CNTD{d}'] = cp - cn
        sa = D(np.abs(dC)).rolling(d).sum().values + e
        F[f'SUMP{d}'] = D(np.fmax(dC, 0)).rolling(d).sum().values / sa
        F[f'SUMN{d}'] = D(np.fmax(-dC, 0)).rolling(d).sum().values / sa
        _sp = D(np.fmax(dC, 0)).rolling(d).sum().values / sa; _sn = D(np.fmax(-dC, 0)).rolling(d).sum().values / sa; F[f'SUMD{d}'] = _sp - _sn
        F[f'VMA{d}'] = rv.mean().values / (V + e)
        F[f'VSTD{d}'] = rv.std().values / (V + e)
        aw = np.abs(C / ref(C, 1) - 1) * V
        F[f'WVMA{d}'] = D(aw).rolling(d).std().values / (D(aw).rolling(d).mean().values + e)
        sva = D(np.abs(dV)).rolling(d).sum().values + e
        F[f'VSUMP{d}'] = D(np.fmax(dV, 0)).rolling(d).sum().values / sa * 0 + D(np.fmax(dV, 0)).rolling(d).sum().values / sva
        F[f'VSUMD{d}'] = (D(np.fmax(dV, 0)).rolling(d).sum().values - D(np.fmax(-dV, 0)).rolling(d).sum().values) / sva
r = pd.DataFrame(rows).sort_values('뒤_20일_t', ascending=False)
r.to_csv('qlib158.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 20)
print('검정', len(r), '| 뒤 20일 t>=3.5:', (r['뒤_20일_t'] >= 3.5).sum(), '| 뒤 20일 양수:', (r['뒤_20일'] > 0).sum())
print(r.head(20).round(3).to_string(index=False)); print(r.tail(5).round(3).to_string(index=False))
