"""변동성 돌파 k=0.5 — ETF 전체(파생·현금성 제외, 500일↑). 각 ETF: 전략 Sharpe vs 보유, vs 같은 진입일 수 무작위 '시가→익일시가'(200회).
+ 진입일 이점 분해: 진입가→익일시가 = (진입가→종가) + (종가→익일시가)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/mnt/user-data/uploads/loop/references/scripts')
from universe_filters import is_deriv, is_cash
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/panel_ohlc_long.csv', dtype={'code': str})
nm = p.drop_duplicates('code', keep='last').set_index('code').name
def perf(r):
    r = np.nan_to_num(r); eq = np.cumprod(1 + r); y = len(r) / 245
    return (eq[-1] ** (1 / y) - 1) * 100, (eq / np.maximum.accumulate(eq) - 1).min() * 100, r.mean() / r.std() * np.sqrt(245) if r.std() > 0 else 0
rng = np.random.default_rng(9); out = []
for code, g in p.groupby('code'):
    if is_deriv(nm[code]) or is_cash(nm[code]) or len(g) < 500: continue
    g = g.sort_values('date'); O, H, L, C = (g[c].values.astype(float) for c in ('open', 'high', 'low', 'close'))
    if (O <= 0).any() or not np.isfinite(O).all(): continue
    trig = O + .5 * np.r_[np.nan, (H - L)[:-1]]; hit = ((H >= trig) & (trig > O))[:-1]
    r = np.where(hit, O[1:] / trig[:-1] - 1, 0.0); on = O[1:] / O[:-1] - 1; bh = C[1:] / C[:-1] - 1
    s = perf(r)[2]; n = hit.sum()
    sims = np.array([perf(np.where(np.isin(np.arange(len(r)), rng.choice(len(r), n, replace=False)), on, 0))[2] for _ in range(200)])
    k3 = len(r) // 3
    out.append(dict(code=code, 이름=nm[code], 일수=len(r), 진입률=n / len(r) * 100, Sh=s, 보유Sh=perf(bh)[2], 무작위중앙=np.median(sims), p=(sims >= s).mean(),
                    건평균=r[hit].mean() * 100, 진입_종가=(C[:-1][hit] / trig[:-1][hit] - 1).mean() * 100, 종가_익일시가=(O[1:][hit] / C[:-1][hit] - 1).mean() * 100,
                    분할Sh='/'.join(f'{perf(r[i*k3:(i+1)*k3])[2]:.2f}' for i in range(3))))
o = pd.DataFrame(out); pd.set_option('display.width', 250)
print('ETF', len(o), '| Sh>보유', (o.Sh > o.보유Sh).mean().round(3), '| p<0.05', (o.p < .05).mean().round(3), '| p<0.05 기대 0.05', '| 중앙 Sh', o.Sh.median().round(2), '보유', o.보유Sh.median().round(2))
print('건평균 중앙 %.3f · 진입→종가 %.3f · 종가→익일시가 %.3f' % (o.건평균.median(), o['진입_종가'].median(), o['종가_익일시가'].median()))
print(o.sort_values('p').head(12).round(3).to_string(index=False)); o.to_csv('yt_vb_all.csv', index=False)
for kw in ('반도체', '200', '코스닥', '미국', '2차전지', '은행'):
    s = o[o.이름.str.contains(kw)]; print(kw, len(s), 'p<0.05 비율', (s.p < .05).mean().round(2), 'Sh중앙', s.Sh.median().round(2), '보유', s.보유Sh.median().round(2))
