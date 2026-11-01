"""Y1 종가베팅 실행 가능성 점검: 상한가 근처(+25%↑) 제외 · 연도별 · 뒤 절반 비용 후 절대 · 갭 vs 장중 분해 · 거래대금 상위/하위."""
import numpy as np, pandas as pd
src = open('yt_rules.py').read().split("rows = []")[0]
exec(src)
from gh_stats import nw_se
with np.errstate(all='ignore'):
    body = C - O; rng = H - L; upw = H - np.fmax(O, C); chg = r1 * 100
    hi20 = sh(D(H).rolling(20).max().values, 1)
    sig = (VAL >= 3e10) & (body > 0) & (body >= .6 * rng) & (chg >= 5) & (upw <= .25 * rng) & (C > hi20) & LIQ
    sig[:260] = False
    gap = R['익일시가']; oc = (fw(C, 1) / fw(O, 1) - 1) * 100; oc[badw[1]] = np.nan
def rep(name, m):
    t, j = np.where(m & np.isfinite(gap)); g = gap[t, j]; ex = g - UM['익일시가'][t]
    d = pd.DataFrame({'t': t, 'g': g, 'ex': ex, 'oc': oc[t, j]}).groupby('t').mean(); te = d[dates[d.index] > SPLIT]
    yr = pd.Series(d.g.values, index=dates[d.index] // 10000).groupby(level=0).mean().round(2).to_dict()
    print(f'{name}: 건 {len(t)} · 일 {len(d)} · 익일시가 절대 {g.mean():.2f}% (비용후 {g.mean()-0.25:.2f}) · 초과 {d.ex.mean():.2f} t {d.ex.mean()/nw_se(d.ex.values,0):.1f}'
          f' · 뒤절반 절대 {te.g.mean():.2f} (비용후 {te.g.mean()-0.25:.2f}) · 승률 {(g>0).mean()*100:.0f}% · 다음날 시가→종가 {np.nanmean(oc[t,j]):.2f}')
    print('   연도별 절대(신호일 평균):', yr)
rep('Y1 원안', sig)
rep('Y1 상승 5~25%(상한가 근처 제외)', sig & (chg < 25))
rep('Y1 상승 10~25%', sig & (chg >= 10) & (chg < 25))
rep('Y1 상승 5~10%', sig & (chg < 10))
rep('Y1 상승 25%↑(상한가권)', sig & (chg >= 25))
