"""네이버 증권 종목분석 리포트(증권사 애널리스트) 이벤트 검정 — 2026-10-28 (루프 외 · 사용자 요청).
데이터: m.stock.naver.com 리포트 상세(작성일·증권사·투자의견·목표가·직전 목표가·작성일 주가) 2018-11~2026-10. 작성일 기준 PIT.
진입 = 작성일 다음 거래일 시가(장전 발간 리포트의 당일 반응은 놓친다 = 보수적). 참고로 작성일 시가 진입도 병기.
보유 1·5·20·60일 종가. 기준 = 같은 날 유동 유니버스 같은 구간 평균. 비수정가 보정(보유 구간 |일간|>31% 제외)."""
import json, glob, numpy as np, pandas as pd
from gh_stats import nw_se
rows = []
for fn in glob.glob('/tmp/claude-0/naver_rs/detail*.jsonl'):
    for l in open(fn):
        try: rows.append(json.loads(l))
        except Exception: pass
r = pd.DataFrame(rows).drop_duplicates('researchId')
num = lambda s: pd.to_numeric(s.astype(str).str.replace(',', ''), errors='coerce')
r['goal'] = num(r.goalPrice); r['px_field'] = num(r.prevGoalPrice)   # ※ API 의 prevGoalPrice·priceAtWriteDate 는 실제로 작성일 무렵 주가(검증: 종가와 일치)
r['dt'] = r.writeDate.str.replace('-', '').astype(int)
r = r.sort_values(['itemCode', 'brokerName', 'dt'])
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); codes = [str(c).replace('A', '').zfill(6) for c in Z['codes']]
O, C, V = (Z[k].astype(float) for k in 'OCV'); bench = Z['bench'].astype(float); T, N = C.shape; ci = {c: j for j, c in enumerate(codes)}
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
with np.errstate(all='ignore'):
    r1 = np.vstack([np.full((1, N), np.nan), C[1:] / C[:-1] - 1]); bad = np.abs(r1) > 0.31
r = r[r.itemCode.isin(ci)].copy(); r['j'] = r.itemCode.map(ci)
r['t0'] = np.searchsorted(dates, r.dt.values, side='right')      # 다음 거래일
r['tw'] = np.searchsorted(dates, r.dt.values, side='left')       # 작성일 당일(거래일이면)
# 같은 증권사 직전 의견(기간 필터 전에 계산 — 초기 리포트의 직전 이력 보존)
g = r.groupby(['itemCode', 'brokerName'])
r['prev_op'] = g.opinion.shift(); r['prev_dt'] = g.dt.shift()
r['prev'] = g.goal.shift(); r.loc[(r.dt - r.prev_dt) > 10000, 'prev'] = np.nan   # 같은 증권사 직전 목표가(1년 이내)
r = r[(r.t0 > 260) & (r.t0 < T - 2)].copy()
r['px'] = C[np.maximum(r.tw.values - 1, 0), r.j.values]   # 작성일 전 거래일 종가(PIT)
r['gap_up'] = r.goal / r.prev - 1
r['upside'] = r.goal / r.px - 1
H = (1, 5, 20, 60); SPLIT = 20230630
FW = {}
with np.errstate(all='ignore'):
    for h in H:
        e = np.minimum(np.arange(T) + h - 1, T - 1)
        R = (C[e] / O - 1) * 100
        bw = pd.DataFrame(bad.astype(float))[::-1].rolling(h, min_periods=1).max()[::-1].values > 0
        R[bw] = np.nan; R[np.arange(T) + h - 1 > T - 1] = np.nan
        FW[h] = (R, np.nanmean(np.where(LIQ & np.isfinite(R), R, np.nan), 1))
out = []


def ev(name, s, entry='t0'):
    s = s[LIQ[s[entry].values - 1, s.j.values]]
    s = s.sort_values(['j', entry]); s = s[~((s.j == s.j.shift()) & (s[entry] - s[entry].shift() < 5))]   # 같은 종목 5일 내 중복 1건
    if len(s) < 50: out.append(dict(이벤트=name, 건수=len(s))); return
    o = dict(이벤트=name, 건수=len(s))
    for h in H:
        R, um = FW[h]; t0 = s[entry].values; v = R[t0, s.j.values]; ok = np.isfinite(v)
        ex = v[ok] - um[t0[ok]]; dd = pd.DataFrame({'t': t0[ok], 'ex': ex}).groupby('t').ex.mean().sort_index()
        o[f'{h}일'] = ex.mean(); o[f'{h}일_t'] = dd.mean() / nw_se(dd.values, max(h - 1, 0))
        if h == 20:
            k3 = len(dd) // 3; o['20일_3분할'] = '/'.join(f'{dd.values[i*k3:(i+1)*k3].mean():.2f}' for i in range(3))
            o['20일_뒤'] = dd[dates[dd.index] > SPLIT].mean(); o['20일_중앙'] = np.median(ex)
            srt = np.sort(ex)[::-1]; o['20일_상위5%제거'] = srt[int(len(srt) * .05):].mean()
            kx = v[ok] - (bench[np.minimum(t0[ok] + 19, T - 1)] / bench[t0[ok] - 1] - 1) * 100; o['20일_KODEX대비'] = kx.mean()
    out.append(o)


has = r.prev.notna() & (r.prev > 0) & r.goal.notna() & (r.goal > 0)
ev('목표가 상향(같은 증권사)', r[has & (r.gap_up > 0.001)])
ev('목표가 상향 20%↑', r[has & (r.gap_up >= 0.20)])
ev('목표가 상향 50%↑', r[has & (r.gap_up >= 0.50)])
ev('목표가 하향', r[has & (r.gap_up < -0.001)])
ev('목표가 하향 20%↑', r[has & (r.gap_up <= -0.20)])
ev('목표가 유지', r[has & (r.gap_up.abs() <= 0.001)])
first = r.prev_dt.isna() | (r.dt - r.prev_dt > 10000)
ev('증권사 신규·재개 커버리지(1년 공백)', r[first & r.goal.notna()])
ev('신규 커버리지 + Buy', r[first & r.opinion.str.contains('Buy|BUY|매수', na=False)])
down = r.prev_op.str.contains('Buy|BUY|매수', na=False) & ~r.opinion.str.contains('Buy|BUY|매수', na=False) & r.opinion.notna() & (r.opinion != '없음')
ev('투자의견 하향(매수→비매수)', r[down])
upop = ~r.prev_op.str.contains('Buy|BUY|매수', na=True) & r.prev_op.notna() & (r.prev_op != '없음') & r.opinion.str.contains('Buy|BUY|매수', na=False)
ev('투자의견 상향(비매수→매수)', r[upop])
ev('작성일 주가 대비 목표가 괴리 ≥ 50%', r[(r.upside >= 0.5) & r.px.notna()])
ev('작성일 주가 대비 목표가 괴리 ≤ 10%', r[(r.upside <= 0.10) & (r.upside > -1) & r.px.notna()])
ev('한국IR협의회·무의견 리포트', r[r.opinion.isin(['없음']) | r.brokerName.str.contains('IR협의회')])
# 리포트 몰림: 같은 종목 5거래일(작성일 기준) 안에 3건↑ — 세 번째 리포트일
r = r.sort_values(['j', 't0'])
r['n5'] = r.groupby('j').t0.transform(lambda x: pd.Series(x.values).rolling(3).apply(lambda w: w[-1] - w[0] <= 5, raw=True).values)
ev('리포트 몰림(5일 내 3건↑)', r[r.n5 == 1])
# 작성일 시가 진입(참고: 장전 발간 반응 포함)
ev('(참고) 목표가 상향 · 작성일 시가 진입', r[has & (r.gap_up > 0.001) & (r.tw < T - 2) & (dates[np.minimum(r.tw, T - 1)] == r.dt)], entry='tw')
o = pd.DataFrame(out); pd.set_option('display.width', 340); pd.set_option('display.max_columns', 30)
print('리포트', len(r), '건 · 종목', r.itemCode.nunique(), '· 기간', r.dt.min(), '~', r.dt.max())
print(o.round(2).to_string(index=False)); o.to_csv('rs_event.csv', index=False)
