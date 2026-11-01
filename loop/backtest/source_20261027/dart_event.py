"""DART 주요사항보고서 이벤트 검정 — 2026-10-28 (루프 외 · 사용자 요청: GitHub·유튜브 외 추천 출처).
진입 = 공시일(rcept_dt) 다음 거래일 시가(장후 공시 포함 보수적). 보유 1·5·20·60일 종가 청산.
기준 = 같은 날 유동 유니버스(종가≥1,000·20일 평균 거래대금≥10억)의 같은 구간 평균. 비수정가 보정: 보유 구간 |일간|>31% 제외.
정정공시([기재정정] 등) 제외, 같은 종목·같은 유형 20거래일 내 반복은 첫 건만."""
import numpy as np, pandas as pd, sys
sys.path.insert(0, '.')
def nw_se(x, lag):
    x = np.asarray(x, float) - np.mean(x); n = len(x); s = (x * x).mean()
    for k in range(1, min(lag, n - 1) + 1): s += 2 * (1 - k / (lag + 1)) * (x[k:] * x[:-k]).mean()
    return np.sqrt(s / n)
M = np.load('dense_meta.npz', allow_pickle=True); dates = M['dates'].astype(int); codes = [str(c).replace('A', '').zfill(6) for c in M['codes']]
C = np.load('dense_C.npz')['a'].astype(float); O = np.load('dense_O.npz')['a'].astype(float); V = np.load('dense_V.npz')['a'].astype(float)
T, N = C.shape; ci = {c: j for j, c in enumerate(codes)}
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
with np.errstate(all='ignore'):
    r1 = np.vstack([np.full((1, N), np.nan), C[1:] / C[:-1] - 1]); bad = np.abs(r1) > 0.31
d = pd.read_csv('dart_B.csv', dtype=str)
d = d[~d.report_nm.str.contains(r'\[')].copy()
d['k'] = d.report_nm.str.replace('주요사항보고서', '').str.strip(' ()')
d['code'] = d.stock_code.fillna('').str.zfill(6)
d = d[d.code.isin(ci)]
d['dt'] = d.rcept_dt.astype(int)
d['t0'] = np.searchsorted(dates, d.dt.values, side='right')        # 공시일 다음 거래일
d = d[(d.t0 > 260) & (d.t0 < T - 2)]
d['j'] = d.code.map(ci)
SPLIT = 20230630
TYPES = ['자기주식취득결정', '자기주식취득신탁계약체결결정', '자기주식처분결정', '자기주식취득신탁계약해지결정', '무상증자결정', '유상증자결정',
         '전환사채권발행결정', '신주인수권부사채권발행결정', '감자결정', '회사합병결정', '회사분할결정', '타법인주식및출자증권양수결정',
         '타법인주식및출자증권양도결정', '유형자산양수결정', '비유동자산취득결정', '소송등의제기', '자기전환사채매도결정']
H = (1, 5, 20, 60)
FW = {}
with np.errstate(all='ignore'):
    for h in H:
        e = np.minimum(np.arange(T) + h - 1, T - 1)
        R = (C[e] / O - 1) * 100                                    # t0 시가 → t0+h-1 종가
        badw = pd.DataFrame(bad.astype(float))[::-1].rolling(h, min_periods=1).max()[::-1].values > 0
        R[badw] = np.nan; R[np.arange(T) + h - 1 > T - 1] = np.nan
        FW[h] = (R, np.nanmean(np.where(LIQ & np.isfinite(R), R, np.nan), 1))
    gap = (O / np.vstack([np.full((1, N), np.nan), C[:-1]]) - 1) * 100   # 공시 다음날 갭(참고)
rows = []
for k in TYPES:
    s = d[d.k == k].sort_values(['j', 't0'])
    s = s[~((s.j == s.j.shift()) & (s.t0 - s.t0.shift() < 20))]           # 20일 내 반복 제거
    s = s[LIQ[s.t0.values - 1, s.j.values]]                              # 공시일 기준 유동 종목
    if len(s) < 30: rows.append(dict(유형=k, 건수=len(s))); continue
    o = dict(유형=k, 건수=len(s), 다음날갭=np.nanmean(gap[s.t0.values, s.j.values]))
    for h in H:
        R, um = FW[h]; v = R[s.t0.values, s.j.values]; ok = np.isfinite(v)
        ex = v[ok] - um[s.t0.values[ok]]; tt = s.t0.values[ok]
        dd = pd.DataFrame({'t': tt, 'ex': ex}).groupby('t').ex.mean().sort_index()
        o[f'{h}일'] = ex.mean(); o[f'{h}일_t'] = dd.mean() / nw_se(dd.values, max(h - 1, 0)) if len(dd) > 20 else np.nan
        if h == 20:
            k3 = len(dd) // 3; o['20일_3분할'] = '/'.join(f'{dd.values[i*k3:(i+1)*k3].mean():.2f}' for i in range(3))
            o['20일_앞'] = dd[dates[dd.index] <= SPLIT].mean(); o['20일_뒤'] = dd[dates[dd.index] > SPLIT].mean()
            o['20일_승률'] = (v[ok] - um[tt] > 0).mean() * 100; o['20일_중앙'] = np.median(ex)
    rows.append(o)
r = pd.DataFrame(rows); pd.set_option('display.width', 320); pd.set_option('display.max_columns', 30)
print('기간', dates[260], '~', dates[-2]); print(r.round(2).to_string(index=False)); r.to_csv('dart_event.csv', index=False)
