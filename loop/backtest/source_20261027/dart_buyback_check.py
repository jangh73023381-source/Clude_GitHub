"""자사주 취득(직접+신탁) 강건성: 연도별 · 상위 5% 건 제거 · 규모(거래대금 순위) 3분위 · KODEX200 대비 · 진입 지연(공시 후 2·5일) · 60일."""
import numpy as np, pandas as pd
exec(open('dart_event.py').read().split("rows = []")[0])
s = d[d.k.isin(['자기주식취득결정', '자기주식취득신탁계약체결결정'])].sort_values(['j', 't0'])
s = s[~((s.j == s.j.shift()) & (s.t0 - s.t0.shift() < 20))]
s = s[LIQ[s.t0.values - 1, s.j.values]]
bench = M['bench'].astype(float)
def ev(tag, ss, h=60, lag=0):
    t0 = ss.t0.values + lag; ok0 = t0 < T - h; t0 = t0[ok0]; jj = ss.j.values[ok0]
    R, um = FW[h]; v = R[t0, jj]; ok = np.isfinite(v); ex = v[ok] - um[t0[ok]]
    kx = v[ok] - (bench[np.minimum(t0[ok] + h - 1, T - 1)] / bench[t0[ok] - 1] - 1) * 100
    dd = pd.DataFrame({'t': t0[ok], 'ex': ex}).groupby('t').ex.mean(); srt = np.sort(ex)[::-1]
    yr = pd.Series(ex, index=dates[t0[ok]] // 10000).groupby(level=0).mean().round(2).to_dict()
    print(f'{tag} | {h}일 n={ok.sum()} 초과 {ex.mean():.2f} t {dd.mean()/nw_se(dd.values, h-1):.2f} 중앙 {np.median(ex):.2f} 상위5%제거 {srt[int(len(srt)*.05):].mean():.2f} KODEX대비 {kx.mean():.2f} | 연도 {yr}')
ev('자사주 전체', s, 20); ev('자사주 전체', s, 60)
ev('자사주 공시 후 2일 지연 진입', s, 60, 2); ev('자사주 5일 지연', s, 60, 5)
rk = pd.DataFrame(val20).rank(axis=1, ascending=False).values
s['rk'] = rk[s.t0.values - 1, s.j.values]
ev('대형(거래대금 상위 200)', s[s.rk <= 200], 60); ev('중형(201~600)', s[(s.rk > 200) & (s.rk <= 600)], 60); ev('소형(601~)', s[s.rk > 600], 60)
ev('직접 취득만', s[s.k == '자기주식취득결정'], 60); ev('신탁만', s[s.k != '자기주식취득결정'], 60)
