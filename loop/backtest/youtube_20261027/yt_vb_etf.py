"""래리 윌리엄스 변동성 돌파 — KODEX200·TIGER200·코스닥150·반도체 ETF. 진입가 = 시가 + k×전일 범위(고가 도달 시), 익일 시가 청산.
대조: (a) 보유 (b) 매일 시가 매수→익일 시가(무조건) (c) 같은 진입일 수를 무작위로 뽑은 '시가→익일시가'(진입가 이점 제거) 1,000회."""
import numpy as np, pandas as pd
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/panel_ohlc_long.csv', dtype={'code': str})
def perf(r):
    r = np.nan_to_num(r); eq = np.cumprod(1 + r); y = len(r) / 245
    return (eq[-1] ** (1 / y) - 1) * 100, (eq / np.maximum.accumulate(eq) - 1).min() * 100, r.mean() / r.std() * np.sqrt(245) if r.std() > 0 else 0
rng = np.random.default_rng(3); out = []
for code, nm in (('069500', 'KODEX200'), ('102110', 'TIGER200'), ('229200', 'KODEX코스닥150'), ('091160', 'KODEX반도체')):
    k_ = p[p.code == code].sort_values('date'); O, H, L, C = (k_[c].values.astype(float) for c in ('open', 'high', 'low', 'close'))
    if len(C) < 500: continue
    on = np.r_[O[1:] / O[:-1] - 1, np.nan]; bh = np.r_[C[1:] / C[:-1] - 1, np.nan]
    ma = pd.Series(C).rolling(5).mean().values
    for k in (0.3, 0.5, 0.7):
        trig = O + k * np.r_[np.nan, (H - L)[:-1]]; hit = (H >= trig) & (trig > O)
        for filt, f in (('', np.ones(len(C), bool)), (' +전일종가>MA5', np.r_[False, (C > ma)[:-1]])):
            h = hit & f
            r = np.where(h, np.r_[O[1:], np.nan] / trig - 1, 0.0)[:-1]
            cg, md, s = perf(r); n = h[:-1].sum()
            sims = [perf(np.where(np.isin(np.arange(len(r)), rng.choice(len(r), n, replace=False)), on[:-1], 0))[2] for _ in range(300)]
            out.append(dict(ETF=nm, k=k, 필터=filt, 진입일=int(n), 진입률=n / len(r) * 100, 건평균=r[h[:-1]].mean() * 100, 승률=(r[h[:-1]] > 0).mean() * 100,
                            CAGR=cg, MDD=md, Sharpe=s, 보유_CAGR=perf(bh[:-1])[0], 보유_MDD=perf(bh[:-1])[1], 보유_Sharpe=perf(bh[:-1])[2],
                            무작위Sharpe중앙=np.median(sims), p=(np.array(sims) >= s).mean(),
                            비용후_건평균=r[h[:-1]].mean() * 100 - 0.03))
o = pd.DataFrame(out); pd.set_option('display.width', 300); pd.set_option('display.max_columns', 20)
print(p.date.min(), '~', p.date.max()); print(o.round(3).to_string(index=False)); o.to_csv('yt_vb_etf.csv', index=False)
