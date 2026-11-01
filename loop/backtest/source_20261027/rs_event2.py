"""리포트 이벤트 — 커버리지 유니버스 기준 재검정. 기준 = 같은 날 '최근 250거래일 안에 리포트가 1건↑ 있던 유동 종목' 평균(같은 구간)."""
import numpy as np, pandas as pd
src = open('rs_event.py').read().split("out = []")[0]
exec(src)
from gh_stats import nw_se
COV = np.zeros((T, N), bool)
for j, tt in r.groupby('j').tw:
    for t in tt.values:
        COV[t:min(t + 250, T), j] = True
COV &= LIQ
UMC = {h: np.nanmean(np.where(COV & np.isfinite(FW[h][0]), FW[h][0], np.nan), 1) for h in H}
out = []
def ev(name, s, entry='t0'):
    s = s[LIQ[s[entry].values - 1, s.j.values]].sort_values(['j', entry]); s = s[~((s.j == s.j.shift()) & (s[entry] - s[entry].shift() < 5))]
    o = dict(이벤트=name, 건수=len(s))
    for h in (5, 20, 60):
        R, _ = FW[h]; t0 = s[entry].values; v = R[t0, s.j.values]; ok = np.isfinite(v)
        ex = v[ok] - UMC[h][t0[ok]]; dd = pd.DataFrame({'t': t0[ok], 'ex': ex}).groupby('t').ex.mean().sort_index()
        o[f'{h}일'] = ex.mean(); o[f'{h}일_t'] = dd.mean() / nw_se(dd.values, h - 1)
        if h in (20, 60):
            srt = np.sort(ex)[::-1]; o[f'{h}일_중앙'] = np.median(ex); o[f'{h}일_상위5%제거'] = srt[int(len(srt) * .05):].mean()
            k3 = len(dd) // 3; o[f'{h}일_3분할'] = '/'.join(f'{dd.values[i*k3:(i+1)*k3].mean():.2f}' for i in range(3))
    out.append(o)
has = r.prev.notna() & (r.prev > 0) & r.goal.notna() & (r.goal > 0)
ev('목표가 상향', r[has & (r.gap_up > 0.001)]); ev('목표가 상향 20%↑', r[has & (r.gap_up >= 0.2)]); ev('목표가 상향 50%↑', r[has & (r.gap_up >= 0.5)])
ev('목표가 유지(대조)', r[has & (r.gap_up.abs() <= 0.001)])
ev('목표가 하향', r[has & (r.gap_up < -0.001)]); ev('목표가 하향 20%↑', r[has & (r.gap_up <= -0.2)])
first = r.prev_dt.isna() | (r.dt - r.prev_dt > 10000)
ev('신규·재개 커버리지', r[first & r.goal.notna()])
ev('괴리 ≥ 50%', r[(r.upside >= .5)]); ev('괴리 ≤ 10%', r[(r.upside <= .1) & (r.upside > -1)])
ev('리포트 몰림(5일 내 3건↑)', r.sort_values(['j', 't0']).assign(n5=lambda x: x.groupby('j').t0.transform(lambda y: pd.Series(y.values).rolling(3).apply(lambda w: w[-1] - w[0] <= 5, raw=True).values)).query('n5 == 1'))
o = pd.DataFrame(out); pd.set_option('display.width', 320); pd.set_option('display.max_columns', 30)
print(o.round(2).to_string(index=False)); o.to_csv('rs_event_cov.csv', index=False)
