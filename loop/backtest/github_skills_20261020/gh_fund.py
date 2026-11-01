"""GitHub 재무 전략 7종 — 분기 리밸런싱(_factor_panel 25시점, 공시마감 후), 시총·주식수는 _krx_pit PIT.
보유 20일·60일(≈다음 리밸런싱). 기준 = 같은 날 '유동 ∩ 재무보유' 종목 동일가중."""
import numpy as np, pandas as pd, pickle
from gh_stats import summarize
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); codes = Z['codes']; C, V = Z['C'], Z['V']; bench = Z['bench']
T, N = C.shape; ci = {c: j for j, c in enumerate(codes)}
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
f = pd.read_csv('/mnt/user-data/uploads/loop/backtest/_factor_panel.csv', dtype={'code': str})
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/_krx_pit.csv', dtype={'code': str})[['date', 'code', 'mktcap', 'shrs']]
f = f.drop(columns=['mktcap']).merge(p, left_on=['rb', 'code'], right_on=['date', 'code'], how='inner')
f = f.sort_values(['code', 'rb'])
g = f.groupby('code')
f['ta_y'] = g.ta.shift(4); f['tl_y'] = g.tl.shift(4); f['shrs_y'] = g.shrs.shift(4); f['rb_y'] = g.rb.shift(4)
f['sag'] = f.sa / f.sa_p - 1; f['sag_prev'] = g.sag.shift(1)
with np.errstate(divide='ignore', invalid='ignore'):
    f['per'] = np.where(f.ni > 0, f.mktcap / f.ni, np.nan); f['pbr'] = np.where(f['eq'] > 0, f.mktcap / f['eq'], np.nan)
    f['de'] = np.where(f['eq'] > 0, f.tl / f['eq'], np.nan); f['roe'] = np.where(f['eq'] > 0, f.ni / f['eq'], np.nan)
    f['opm'] = f.op / f.sa; f['opm_p'] = f.op_p / f.sa_p; f['nig'] = np.where(f.ni_p > 0, f.ni / f.ni_p - 1, np.nan)
    f['ey'] = f.op / (f.mktcap + f.tl); f['roc'] = f.op / f.ta
# 거래일 인덱스·유동성
ti = {d: i for i, d in enumerate(dates)}
f['t'] = f.rb.map(lambda d: ti.get(d, np.searchsorted(dates, d)))
f['j'] = f.code.map(ci); f = f.dropna(subset=['j']); f['j'] = f.j.astype(int)
f = f[f.t < T - 1]
f['liq'] = LIQ[f.t.values, f.j.values]; f = f[f.liq]
for h in (20, 60):
    tt = np.minimum(f.t.values + h, T - 1)
    f[f'r{h}'] = (C[tt, f.j.values] / C[f.t.values, f.j.values] - 1) * 100
    f[f'k{h}'] = (bench[tt] / bench[f.t.values] - 1) * 100
    f.loc[f.t.values + h > T - 1, f'r{h}'] = np.nan

S = {}
S['Graham 방어적(ai-hedge-fund)'] = (f.ni > 0) & (f.ni_p > 0) & (f.per <= 15) & (f.pbr <= 1.5) & (f.per * f.pbr <= 22.5) & (f.de <= 1.0)
S['Buffett·Munger 품질+적정가'] = (f.roe >= .15) & (f.opm >= .15) & (f.de <= .5) & (f.per <= 25) & (f.ni >= f.ni_p)
S['Lynch GARP(PEG<1)'] = (f.nig >= .20) & (f.per / (f.nig * 100) <= 1) & (f.de <= 1.0)
S['Druckenmiller 매출가속·마진개선'] = (f.sag > 0) & (f.sag >= f.sag_prev + .05) & (f.opm > f.opm_p)
S['Dhandho(한국 저장소, FCF 제외 3축)'] = (f.de <= .5) & (f.roe >= .15) & ((f.per <= 15) | (f.ey >= .08))
mf = (f.mktcap >= 5e10) & (f.op > 0)
f['mf_rank'] = np.nan
for rb, gg in f[mf].groupby('rb'):
    f.loc[gg.index, 'mf_rank'] = gg['ey'].rank(ascending=False) + gg.roc.rank(ascending=False)
f['mf_top'] = f.groupby('rb').mf_rank.rank(method='first') <= 30
S['Greenblatt 마법공식 상위30'] = f.mf_top & mf
fs = ((f.ni / f.ta > 0).astype(int) + (f.ni / f.ta > f.ni_p / f.ta_y).astype(int) + (f.tl / f.ta < f.tl_y / f.ta_y).astype(int)
      + (f.opm > f.opm_p).astype(int) + (f.sa / f.ta > f.sa_p / f.ta_y).astype(int) + (f.shrs <= f.shrs_y).astype(int))
f['fs'] = np.where(f.ta_y.notna(), fs, np.nan)
pb_low = f.groupby('rb').pbr.rank(pct=True) <= .2
S['Piotroski-lite ≥5/6 (전체)'] = f.fs >= 5
S['Piotroski-lite ≥5/6 (저PBR 20%)'] = (f.fs >= 5) & pb_low

R = []
for h in (60, 20):
    um = f.groupby('t')[f'r{h}'].mean()
    for nm, m in S.items():
        s = f[m & f[f'r{h}'].notna()]
        ex = s[f'r{h}'].values - um.reindex(s.t).values
        kx = (s[f'r{h}'] - s[f'k{h}']).groupby(s.t).mean().mean()
        R.append(summarize(f'{nm} | {h}일', s.t.values, ex, 0, {'종목/회': round(len(s) / s.t.nunique(), 1), 'KODEX대비': kx}))
r = pd.DataFrame(R); pd.set_option('display.width', 300); pd.set_option('display.max_columns', 30)
print('리밸런싱', f.rb.nunique(), '유니버스/회', round(len(f) / f.rb.nunique()))
print(r.round(2).to_string(index=False)); r.to_csv('gh_fund_summary.csv', index=False)
f.to_pickle('gh_fund_panel.pkl'); pickle.dump({k: v.values for k, v in S.items()}, open('gh_fund_masks.pkl', 'wb'))
