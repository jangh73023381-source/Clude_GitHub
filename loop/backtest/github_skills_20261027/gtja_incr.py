"""GTJA 상위 알파의 증분 검정: 기존 신호(PVC=−corr(H,V,10) [Alpha101 계열·10/20 보류 구성], 저변동 σ20, 5일 반전, 12-1 모멘텀)를
횡단면 순위 회귀(Fama-MacBeth)로 통제한 뒤 알파 계수가 남는가. 표본 = 5거래일 간격, 유동 종목, 뒤 절반(2023-07~).
+ 상위 10% 의 KODEX200 대비 20일 초과(뒤 절반) — '유니버스는 이기나 지수는 못 이긴다' 구조 확인."""
import sys, numpy as np, pandas as pd, pickle
sys.path.insert(0, '/tmp/claude-0/vcpkr')
from gh_stats import nw_se
from gtja_ops import load_compute
Z = np.load('dense.npz'); dates = Z['dates'].astype(int)
O, H, L, C, V = (Z[k].astype(float) for k in 'OHLCV'); T, N = C.shape; bench = Z['bench'].astype(float)
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9); keep = LIQ.any(0)
O, H, L, C, V, LIQ, val20 = O[:, keep], H[:, keep], L[:, keep], C[:, keep], V[:, keep], LIQ[:, keep], val20[:, keep]; N = C.shape[1]
idx = pd.to_datetime(dates.astype(str)); cols = [str(i) for i in range(N)]
Df = lambda A: pd.DataFrame(A, index=idx, columns=cols)
panel = dict(open=Df(O), high=Df(H), low=Df(L), close=Df(C), volume=Df(V), amount=Df(C * V), vwap=Df((O + H + L + C) / 4),
             benchmark_close=Df(np.repeat(bench[:, None], N, 1)))
F20 = np.vstack([C[20:] / C[:-20] - 1, np.full((20, N), np.nan)]) * 100
K20 = np.r_[(bench[20:] / bench[:-20] - 1) * 100, np.full(20, np.nan)]
with np.errstate(all='ignore'):
    r1 = np.vstack([np.full((1, N), np.nan), C[1:] / C[:-1] - 1])
    ctrl = dict(PVC=-Df(H).rolling(10).corr(Df(V)).values,
                LOWVOL=-pd.DataFrame(r1).rolling(20, min_periods=15).std().values,
                REV5=-(C / np.vstack([np.full((5, N), np.nan), C[:-5]]) - 1),
                MOM=np.vstack([np.full((252, N), np.nan), C[231:T - 21] / C[:T - 252]]) - 1,
                SIZE=-np.log(val20))
r = pd.read_csv('gtja191.csv')
top = r[r['뒤_20일_t'] >= 3.5]
ts = [t for t in range(260, T - 20, 5) if dates[t] > 20230630]
rk = lambda x: pd.Series(x).rank(pct=True).values - .5
out = []
for _, row in top.iterrows():
    k = row['알파']; sgn = 1 if row['방향'] == '높을수록' else -1
    with np.errstate(all='ignore'):
        X = load_compute(f'/tmp/claude-0/ext/HKUDS_Vibe-Trading/agent/src/factors/zoo/gtja191/{k}.py')(panel)
    X = sgn * X.reindex(index=idx, columns=cols).values.astype(float)
    b_raw, b_ctl, kx, corr_pvc = [], [], [], []
    for t in ts:
        m = LIQ[t] & np.isfinite(X[t]) & np.isfinite(F20[t])
        for c in ctrl.values(): m &= np.isfinite(c[t])
        if m.sum() < 200: continue
        y = rk(F20[t, m]); a = rk(X[t, m]); Xc = np.column_stack([a] + [rk(c[t, m]) for c in ctrl.values()] + [np.ones(m.sum())])
        b_raw.append(np.polyfit(a, y, 1)[0]); b_ctl.append(np.linalg.lstsq(Xc, y, rcond=None)[0][0])
        corr_pvc.append(np.corrcoef(a, rk(ctrl['PVC'][t, m]))[0, 1])
        q = X[t, m] >= np.quantile(X[t, m], .9); kx.append(F20[t, m][q].mean() - K20[t])
    b_raw, b_ctl, kx = map(np.array, (b_raw, b_ctl, kx))
    out.append(dict(알파=k, 원_t=row['뒤_20일_t'], PVC상관=np.mean(corr_pvc), 단순계수_t=b_raw.mean() / nw_se(b_raw, 3),
                    통제후계수=b_ctl.mean(), 통제후_t=b_ctl.mean() / nw_se(b_ctl, 3), 통제후_유지비=b_ctl.mean() / b_raw.mean(),
                    상위10_KODEX대비_20일=kx.mean(), 상위10_KODEX대비_t=kx.mean() / nw_se(kx, 3)))
    print(out[-1], flush=True)
o = pd.DataFrame(out); o.to_csv('gtja_incr.csv', index=False)
pd.set_option('display.width', 250); print(o.round(3).to_string(index=False))
