import sys, os, numpy as np, pandas as pd
sys.path.insert(0, 'references/scripts'); from universe_filters import is_deriv, is_cash
p = pd.read_csv('backtest/_vb_krx_etf_ohlc.csv', dtype={'code': str})
for c in ('open', 'high', 'low', 'close', 'value'): p[c] = pd.to_numeric(p[c], errors='coerce')
cl = p.pivot(index='date', columns='code', values='close')
dup = (cl.diff().abs().sum(1) == 0)          # 휴장일(직전 값 반복)
keep = cl.index[~dup]; p = p[p.date.isin(keep)]
nm = pd.read_csv('backtest/krx_etf_panel.csv', dtype={'code': str}, usecols=['code', 'name']).drop_duplicates('code', keep='last').set_index('code').name
def perf(r):
    r = np.nan_to_num(r); eq = np.cumprod(1 + r); y = len(r) / 245
    return (eq[-1] ** (1 / y) - 1) * 100, (eq / np.maximum.accumulate(eq) - 1).min() * 100, r.mean() / r.std() * np.sqrt(245) if r.std() > 0 else 0
rng = np.random.default_rng(9); out = []
for code, g in p.groupby('code'):
    n_ = nm.get(code, '')
    if not n_ or is_deriv(n_) or is_cash(n_) or len(g) < 400: continue
    g = g.sort_values('date'); O, H, L, C, Vv = (g[c].values.astype(float) for c in ('open', 'high', 'low', 'close', 'value'))
    if (O <= 0).any() or np.median(Vv) < 5e8: continue           # 하루 거래대금 중앙 5억 미만 제외(체결 현실성)
    trig = O + .5 * np.r_[np.nan, (H - L)[:-1]]; hit = ((H >= trig) & (trig > O))[:-1]
    r = np.where(hit, O[1:] / trig[:-1] - 1, 0.0); on = O[1:] / O[:-1] - 1; bh = C[1:] / C[:-1] - 1
    s = perf(r)[2]; n = hit.sum()
    sims = np.array([perf(np.where(np.isin(np.arange(len(r)), rng.choice(len(r), n, replace=False)), on, 0))[2] for _ in range(200)])
    out.append(dict(code=code, 이름=n_, 일수=len(r), Sh=s, 보유Sh=perf(bh)[2], p=(sims >= s).mean(), 건평균=r[hit].mean() * 100,
                    진입_종가=(C[:-1][hit] / trig[:-1][hit] - 1).mean() * 100, 종가_익일시가=(O[1:][hit] / C[:-1][hit] - 1).mean() * 100,
                    전체_종가_익일시가=(O[1:] / C[:-1] - 1).mean() * 100))
o = pd.DataFrame(out)
print('KRX 공식 OHLC', keep.min(), '~', keep.max(), '거래일', len(keep), '| ETF', len(o), '| Sh>보유', round((o.Sh > o.보유Sh).mean(), 3), '| p<0.05', round((o.p < .05).mean(), 3))
print('중앙: Sh %.2f 보유 %.2f 건평균 %.3f 진입→종가 %.3f 종가→익일시가 %.3f (전체일 종가→익일시가 %.3f)' % (o.Sh.median(), o.보유Sh.median(), o.건평균.median(), o.진입_종가.median(), o.종가_익일시가.median(), o.전체_종가_익일시가.median()))
for c in ('069500', '102110', '091160', '091230', '229200', '360750', '133690'):
    s = o[o.code == c]
    if len(s): print(s.round(3).to_string(index=False, header=False))
o.to_csv('backtest/_vb_krx_check.csv', index=False)
