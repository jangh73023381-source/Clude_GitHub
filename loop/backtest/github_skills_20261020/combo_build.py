"""조합 검정용 신호 11종 (높을수록 좋음) — 리밸런싱일에서만 쓰지만 일별로 만든다. 재무는 공시마감 후 리밸런싱일부터 ffill(PIT)."""
import numpy as np, pandas as pd, pickle
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); codes = Z['codes']; O, H, L, C, V = (Z[k] for k in 'OHLCV')
T, N = C.shape; ci = {c: j for j, c in enumerate(codes)}
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
D = lambda A: pd.DataFrame(A)
S = {}
with np.errstate(invalid='ignore', divide='ignore'):
    S['NH 신고가근접'] = C / D(H).rolling(250, min_periods=250).max().values
    S['PVC 고가-거래량 상관↓'] = -D(H).rolling(10).corr(D(V)).values
    ret = D(C).pct_change(fill_method=None)
    S['LV 저변동σ20'] = -ret.rolling(20).std().values
    Cs = np.vstack([np.full((21, N), np.nan), C[:-21]]); Cl = np.vstack([np.full((252, N), np.nan), C[:-252]])
    S['MOM 12-1'] = Cs / Cl - 1
    C5 = np.vstack([np.full((5, N), np.nan), C[:-5]])
    S['REV 5일 반전'] = -(C / C5 - 1)
    m50, m150, m200 = (D(C).rolling(n).mean().values for n in (50, 150, 200))
    m200p = np.vstack([np.full((20, N), np.nan), m200[:-20]])
    S['TT 추세템플릿'] = np.where(np.isnan(m200p), np.nan, ((C > m50) & (m50 > m150) & (m150 > m200) & (m200 > m200p)).astype(float))
    S['TV 거래대금순위'] = np.log(val20)
# 재무
f = pd.read_csv('/mnt/user-data/uploads/loop/backtest/_factor_panel.csv', dtype={'code': str})
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/_krx_pit.csv', dtype={'code': str})[['date', 'code', 'shrs']]
f = f.merge(p, left_on=['rb', 'code'], right_on=['date', 'code'], how='left').sort_values(['code', 'rb'])
g = f.groupby('code'); f['ta_y'] = g.ta.shift(4); f['tl_y'] = g.tl.shift(4); f['shrs_y'] = g.shrs.shift(4)
with np.errstate(invalid='ignore', divide='ignore'):
    f['roe'] = np.where(f['eq'] > 0, f.ni / f['eq'], np.nan)
    f['opg'] = np.where(f.op_p > 0, f.op / f.op_p - 1, np.where((f.op > 0) & (f.op_p <= 0), 1.0, np.nan))
    f['opg'] = f.opg.clip(-1, 3)
    fs = ((f.ni / f.ta > 0).astype(int) + (f.ni / f.ta > f.ni_p / f.ta_y).astype(int) + (f.tl / f.ta < f.tl_y / f.ta_y).astype(int)
          + (f.op / f.sa > f.op_p / f.sa_p).astype(int) + (f.sa / f.ta > f.sa_p / f.ta_y).astype(int) + (f.shrs <= f.shrs_y).astype(int))
    f['fs'] = np.where(f.ta_y.notna(), fs, np.nan)
f['t'] = np.searchsorted(dates, f.rb.values); f['j'] = f.code.map(ci); f = f.dropna(subset=['j']); f['j'] = f.j.astype(int)
def ffill_arr(col):
    A = np.full((T, N), np.nan); A[f.t.values.clip(0, T - 1), f.j.values] = f[col].values
    return D(A).ffill(limit=90).values
ni = ffill_arr('ni'); shrs = ffill_arr('shrs')
S['ROE 수익성'] = ffill_arr('roe')
S['OPG 영업이익성장'] = ffill_arr('opg')
with np.errstate(invalid='ignore', divide='ignore'):
    S['EY 이익수익률'] = ni / (shrs * C)
S['PIO Piotroski'] = ffill_arr('fs')
start = int(np.searchsorted(dates, 20200605))
pickle.dump(dict(S=S, LIQ=LIQ, start=start), open('combo_sig.pkl', 'wb'), protocol=4)
for k, v in S.items(): print(k, np.isfinite(v[start:]).mean().round(3))
