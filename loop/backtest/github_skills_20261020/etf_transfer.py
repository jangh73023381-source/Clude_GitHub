"""PVC·조합 신호의 ETF 7년 전이 검정. 유니버스 = universe_filters(파생·현금성 제외), Rule H, pool30(mom20).
A 지표: D 종가 선정 → D→D+1 종가 수익(1일 회전, 비용 0 = v2.8). 20일 트랜치(매일 1/20 겹침) 병기."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/mnt/user-data/uploads/loop/references/scripts')
from universe_filters import is_deriv, is_cash
from gh_stats import nw_se
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/panel_ohlc_long.csv', dtype={'code': str})
names = p.drop_duplicates('code', keep='last').set_index('code').name
P = {k: p.pivot(index='date', columns='code', values=k) for k in ('high', 'close', 'volume')}
dates = P['close'].index.values; codes = P['close'].columns
ok = np.array([not (is_deriv(names[c]) or is_cash(names[c])) for c in codes])
C, Hh, V = (P[k].values[:, ok] for k in ('close', 'high', 'volume')); codes = codes[ok]
kx = list(p.pipe(lambda d: d).query("code=='069500'").sort_values('date').close.values) if False else None
k200 = P['close']['069500'].values
T, N = C.shape
D_ = lambda A: pd.DataFrame(A)
with np.errstate(invalid='ignore', divide='ignore'):
    R1 = np.vstack([np.full((1, N), np.nan), C[1:] / C[:-1] - 1])
    mom20 = C / np.vstack([np.full((20, N), np.nan), C[:-20]]) - 1
    r3 = C / np.vstack([np.full((3, N), np.nan), C[:-3]]) - 1
    ruleH = (R1 > .10) | (r3 > .20)
    sig20 = D_(R1).rolling(20, min_periods=6).std().values
    pvc = -D_(Hh).rolling(10).corr(D_(V)).values
    nh = C / D_(Hh).rolling(250, min_periods=120).max().values
    m50, m150, m200 = (D_(C).rolling(n, min_periods=n).mean().values for n in (50, 150, 200))
    tt = ((C > m50) & (m50 > m150) & (m150 > m200)).astype(float)
F1 = np.vstack([C[1:] / C[:-1] - 1, np.full((1, N), np.nan)]) * 100
KX1 = np.r_[(k200[1:] / k200[:-1] - 1) * 100, np.nan]
start = 260
def rnk(x):
    return pd.Series(x).rank(pct=True).values
def pick(t, how):
    m = np.isfinite(mom20[t]) & ~ruleH[t] & np.isfinite(C[t])
    idx = np.where(m)[0]
    if len(idx) < 30: return None
    pool = idx[np.argsort(-mom20[t, idx])[:30]]
    if how == 'MOM': return pool[:5]
    if how == 'LV': s = -sig20[t, pool]
    elif how == 'PVC_pool': s = pvc[t, pool]
    elif how == 'LV+PVC_pool': s = rnk(-sig20[t, pool]) + rnk(pvc[t, pool])
    elif how == 'LV+NH_pool': s = rnk(-sig20[t, pool]) + rnk(nh[t, pool])
    elif how == 'LV+PVC+NH+TT_pool': s = rnk(-sig20[t, pool]) + rnk(pvc[t, pool]) + rnk(nh[t, pool]) + rnk(tt[t, pool])
    elif how in ('PVC_univ', 'NH+PVC+TT_univ'):
        u = idx
        s = pvc[t, u] if how == 'PVC_univ' else rnk(pvc[t, u]) + rnk(nh[t, u]) + rnk(tt[t, u])
        s = np.where(np.isfinite(s), s, -np.inf); return u[np.argsort(-s)[:5]]
    s = np.where(np.isfinite(s), s, -np.inf)
    return pool[np.argsort(-s)[:5]]
hows = ['MOM', 'LV', 'PVC_pool', 'LV+PVC_pool', 'LV+NH_pool', 'LV+PVC+NH+TT_pool', 'PVC_univ', 'NH+PVC+TT_univ']
ts = list(range(start, T - 1))
daily = {h: [] for h in hows}; picks = {h: {} for h in hows}
for t in ts:
    for h in hows:
        pk = pick(t, h); picks[h][t] = pk
        daily[h].append(np.nanmean(F1[t, pk]) if pk is not None else 0.0)
kd = np.array([KX1[t] for t in ts])
def perf(r):
    r = np.asarray(r) / 100; eq = np.cumprod(1 + r); yrs = len(r) / 245
    return eq[-1] ** (1 / yrs) - 1, (eq / np.maximum.accumulate(eq) - 1).min(), r.mean() / r.std() * np.sqrt(245)
rows = []
lv = np.array(daily['LV'])
for h in hows + ['KODEX200']:
    r = kd if h == 'KODEX200' else np.array(daily[h])
    cg, mdd, sh = perf(r); d = r - lv; n = len(d); k = n // 3; sr = np.sort(d)[::-1]
    rows.append(dict(방법=h, CAGR=cg * 100, MDD=mdd * 100, Sharpe=sh, KODEX초과_일=(r - kd).mean(),
                     LV대비_일=d.mean(), LV대비_t=d.mean() / nw_se(d, 0) if d.std() > 0 else 0,
                     LV대비_fold=f'{d[:k].mean():.3f}/{d[k:2*k].mean():.3f}/{d[2*k:].mean():.3f}', LV대비_상위3일제거=sr[3:].mean()))
# 20일 트랜치(매일 매수, 20일 보유)
F20 = {}
for h in ['LV', 'PVC_pool', 'LV+PVC_pool', 'PVC_univ', 'NH+PVC+TT_univ', 'MOM']:
    port = []
    for t in ts[20:]:
        rs = [np.nanmean(F1[t, picks[h][s]]) for s in range(t - 19, t + 1) if picks[h].get(s) is not None]
        port.append(np.mean(rs) if rs else 0.0)
    F20[h] = np.array(port)
kd20 = kd[20:]
for h, r in F20.items():
    cg, mdd, sh = perf(r); d = r - F20['LV']
    rows.append(dict(방법=h + ' [20일 트랜치]', CAGR=cg * 100, MDD=mdd * 100, Sharpe=sh, KODEX초과_일=(r - kd20).mean(),
                     LV대비_일=d.mean(), LV대비_t=d.mean() / nw_se(d, 19) if d.std() > 0 else 0))
out = pd.DataFrame(rows); pd.set_option('display.width', 250); pd.set_option('display.max_columns', 20)
print('기간', dates[start], '~', dates[T - 2], '일수', len(ts), 'ETF', N)
print(out.round(3).to_string(index=False)); out.to_csv('etf_transfer.csv', index=False)
