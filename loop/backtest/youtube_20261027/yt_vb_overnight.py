"""변동성 돌파 vs '밤에만 보유'(매일 종가 매수→익일 시가). 7년 ETF 패널. 같은 노출로 맞춘 비교: 변동성돌파 진입일만 밤 보유 vs 무작위 같은 일수 밤 보유."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/mnt/user-data/uploads/loop/references/scripts')
from universe_filters import is_deriv, is_cash
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/panel_ohlc_long.csv', dtype={'code': str})
nm = p.drop_duplicates('code', keep='last').set_index('code').name
def sh(r): r = np.nan_to_num(r); return r.mean() / r.std() * np.sqrt(245) if r.std() > 0 else 0
def cg(r): r = np.nan_to_num(r); return (np.prod(1 + r) ** (245 / len(r)) - 1) * 100
rng = np.random.default_rng(4); out = []
for code, g in p.groupby('code'):
    if is_deriv(nm[code]) or is_cash(nm[code]) or len(g) < 500: continue
    g = g.sort_values('date'); O, H, L, C = (g[c].values.astype(float) for c in ('open', 'high', 'low', 'close'))
    if (O <= 0).any(): continue
    trig = O + .5 * np.r_[np.nan, (H - L)[:-1]]; hit = ((H >= trig) & (trig > O))[:-1]
    vb = np.where(hit, O[1:] / trig[:-1] - 1, 0.0); ovn = O[1:] / C[:-1] - 1; intra = C / O - 1
    vb_ovn = np.where(hit, ovn, 0.0)                                   # 진입일의 밤만
    n = hit.sum()
    sims = np.array([sh(np.where(np.isin(np.arange(len(ovn)), rng.choice(len(ovn), n, replace=False)), ovn, 0)) for _ in range(200)])
    out.append(dict(code=code, 이름=nm[code], VB_Sh=sh(vb), 밤만_Sh=sh(ovn), 보유_Sh=sh(C[1:] / C[:-1] - 1), VB_CAGR=cg(vb), 밤만_CAGR=cg(ovn),
                    장중평균=np.nanmean(intra) * 100, 밤평균=np.nanmean(ovn) * 100, VB진입일밤_Sh=sh(vb_ovn), 무작위밤_p=(sims >= sh(vb_ovn)).mean()))
o = pd.DataFrame(out); pd.set_option('display.width', 250)
print('ETF', len(o)); print(o[['VB_Sh', '밤만_Sh', '보유_Sh', 'VB_CAGR', '밤만_CAGR', '장중평균', '밤평균']].median().round(3).to_dict())
print('VB > 밤만 비율', round((o.VB_Sh > o.밤만_Sh).mean(), 3), '| 진입일 밤이 무작위 밤보다 나음(p<0.05)', round((o.무작위밤_p < .05).mean(), 3))
print(o[o.code.isin(['069500', '091160', '091230', '229200', '133690'])].round(3).to_string(index=False)); o.to_csv('yt_vb_overnight.csv', index=False)
