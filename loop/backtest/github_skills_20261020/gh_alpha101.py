"""WorldQuant 101 Alphas (yli188/WorldQuant_alpha101_code) — 수식은 원본 그대로 쓰고 보조함수만 교정:
- rank: 원본은 종목별 '시계열 전체' 순위(미래 정보 누설) → 논문 정의대로 횡단면 순위(axis=1, 원본 주석 처리된 줄)
- ts_rank/ts_argmax/ts_argmin/product/decay_linear: 다종목(wide) 대응 + 속도용 벡터화(정의 동일)
- vwap: 거래대금 없음 → (H+L+C)/3 근사
python3 gh_alpha101.py <shard> <nshard>"""
import sys, importlib.util, time, pickle, signal, numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv
SH, NS = int(sys.argv[1]), int(sys.argv[2])
spec = importlib.util.spec_from_file_location('a101', '/tmp/claude-0/ext/yli188_WorldQuant_alpha101_code/101Alpha_code_1.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)

def _win(df, w, fn):
    x = df.values.astype(float); out = np.full_like(x, np.nan)
    if len(x) >= w:
        for c0 in range(0, x.shape[1], 400):
            v = swv(x[:, c0:c0 + 400], w, axis=0)  # (T-w+1, n, w)
            out[w - 1:, c0:c0 + 400] = fn(v)
    return pd.DataFrame(out, index=df.index, columns=df.columns)
def ts_rank(df, window=10):
    def f(v):
        last = v[..., -1:]; r = (v < last).sum(-1) + ((v == last).sum(-1) + 1) / 2
        r = r.astype(float); r[np.isnan(v).any(-1)] = np.nan; return r
    return _win(df, int(window), f)
def ts_argmax(df, window=10):
    return _win(df, int(window), lambda v: np.where(np.isnan(v).any(-1), np.nan, np.argmax(np.nan_to_num(v, nan=-np.inf), -1) + 1.))
def ts_argmin(df, window=10):
    return _win(df, int(window), lambda v: np.where(np.isnan(v).any(-1), np.nan, np.argmin(np.nan_to_num(v, nan=np.inf), -1) + 1.))
def product(df, window=10):
    return _win(df, int(window), lambda v: np.prod(v, -1))
def decay_linear(df, period=10):
    period = int(period); w = np.arange(1, period + 1, dtype=float); w /= w.sum()
    return _win(df.ffill().bfill() if False else df, period, lambda v: (v * w).sum(-1))
def rank(df):
    return df.rank(axis=1, pct=True)
for k, fn in dict(ts_rank=ts_rank, ts_argmax=ts_argmax, ts_argmin=ts_argmin, product=product, decay_linear=decay_linear, rank=rank).items():
    setattr(A, k, fn)

Z = np.load('dense.npz'); dates = Z['dates']; O, H, L, C, V = (Z[k] for k in 'OHLCV'); T, N = C.shape
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
keep = LIQ.sum(0) >= 120; LIQk = LIQ[:, keep]
mk = lambda X: pd.DataFrame(X[:, keep])
d = {'S_DQ_OPEN': mk(O), 'S_DQ_HIGH': mk(H), 'S_DQ_LOW': mk(L), 'S_DQ_CLOSE': mk(C), 'S_DQ_VOLUME': mk(V) / 100,
     'S_DQ_PCTCHANGE': mk(C).pct_change(fill_method=None), 'S_DQ_AMOUNT': mk(V) / 1000}
al = A.Alphas(d)
al.vwap = (mk(H) + mk(L) + mk(C)) / 3
Ck = C[:, keep]
F1 = np.vstack([Ck[1:] / Ck[:-1] - 1, np.full((1, Ck.shape[1]), np.nan)]) * 100
F5 = np.vstack([Ck[5:] / Ck[:-5] - 1, np.full((5, Ck.shape[1]), np.nan)]) * 100
names = sorted(m for m in dir(al) if m.startswith('alpha'))[SH::NS]

class TO(Exception): pass
def _h(*a): raise TO()
signal.signal(signal.SIGALRM, _h)
res = {}
for nm in names:
    t0 = time.time()
    try:
        signal.alarm(240)
        a = getattr(al, nm)()
        signal.alarm(0)
        a = np.asarray(a.values if hasattr(a, 'values') else a, float)
        if a.shape != Ck.shape: raise ValueError(f'shape {a.shape}')
    except Exception as e:
        signal.alarm(0); res[nm] = ('ERR', repr(e)[:80]); print(nm, 'ERR', repr(e)[:80], flush=True); continue
    ex1, ex5, ic, to, prev = [], [], [], [], None
    for t in range(260, T - 5):
        m = LIQk[t] & np.isfinite(a[t]) & np.isfinite(F1[t])
        if m.sum() < 100: ex1.append(np.nan); ex5.append(np.nan); ic.append(np.nan); continue
        x = a[t, m]; q = x >= np.quantile(x, .9)
        if q.mean() > .5: ex1.append(np.nan); ex5.append(np.nan); ic.append(np.nan); continue  # 상수/동률 과다
        ex1.append(F1[t, m][q].mean() - F1[t, m].mean())
        f5 = F5[t, m]; ok = np.isfinite(f5); ex5.append(np.nanmean(f5[q & ok]) - np.nanmean(f5[ok]))
        ic.append(pd.Series(x).corr(pd.Series(F1[t, m]), method='spearman'))
        sel = set(np.where(m)[0][q]); to.append(1 - len(sel & prev) / len(sel) if prev else np.nan); prev = sel
    res[nm] = (np.array(ex1), np.array(ex5), np.array(ic), np.nanmean(to))
    print(nm, round(time.time() - t0, 1), 's', round(np.nanmean(ex1), 4), flush=True)
pickle.dump(res, open(f'a101_{SH}.pkl', 'wb'))
