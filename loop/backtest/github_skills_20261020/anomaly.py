"""OpenSourceAP/CrossSection(Chen–Zimmermann) 신호 중 미시도 ~30개 — SignalDoc.csv 정의·부호를 한국 데이터에 맞춰 근사.
월(20거래일) 1회, 신호 방향 상위 10% 동일가중 20일 보유 vs 같은 날 유동 유니버스(신호 보유 종목) 동일가중.
오프셋 0·10 두 경로. 앞(~2023-06)/뒤 분리. 근사: 1개월=21거래일, 시장=유동 동일가중, EPS→영업이익, 재무는 공시마감 후 PIT."""
import numpy as np, pandas as pd, pickle, gc
from gh_stats import nw_se
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); codes = Z['codes']; O, H, L, C, V = (Z[k] for k in 'OHLCV')
bench = Z['bench']; T, N = C.shape; ci = {c: j for j, c in enumerate(codes)}
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
D = lambda A: pd.DataFrame(A)
sh = lambda A, k: np.vstack([np.full((k, N), np.nan), A[:-k]])
with np.errstate(invalid='ignore', divide='ignore'):
    R = C / sh(C, 1) - 1
mkt = np.array([np.nanmean(np.where(LIQ[t - 1] if t else LIQ[t], R[t], np.nan)) if t else np.nan for t in range(T)])
M = np.repeat(mkt[:, None], N, 1)
# ---- 재무 PIT (combo_build 와 같은 방식) ----
f = pd.read_csv('/mnt/user-data/uploads/loop/backtest/_factor_panel.csv', dtype={'code': str})
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/_krx_pit.csv', dtype={'code': str})[['date', 'code', 'shrs']]
f = f.merge(p, left_on=['rb', 'code'], right_on=['date', 'code'], how='left').sort_values(['code', 'rb'])
g = f.groupby('code')
for c_ in ('ta', 'tl', 'eq', 'shrs', 'sa', 'ni', 'op'):
    f[c_ + '_y'] = g[c_].shift(4)
f['t'] = np.searchsorted(dates, f.rb.values); f['j'] = f.code.map(ci); f = f.dropna(subset=['j']); f['j'] = f.j.astype(int)
def ff(vals):
    A = np.full((T, N), np.nan); A[f.t.values.clip(0, T - 1), f.j.values] = vals
    return D(A).ffill(limit=90).values
fq = pd.read_csv('/mnt/user-data/uploads/loop/backtest/sjh/fund.csv', dtype={'code': str})
qord = {11013: 1, 11012: 2, 11014: 3, 11011: 4}
fq['q'] = fq.reprt.map(qord)
# 사업보고서(11011)는 연간 누적 → 4분기 단일값 = 연간 − (1~3분기)
w = fq.pivot_table(index=['code', 'year'], columns='q', values=['sa', 'op'])
for v in ('sa', 'op'):
    q4 = w[(v, 4)] - w[(v, 1)] - w[(v, 2)] - w[(v, 3)]
    fq = fq.merge(q4.rename(v + '_q4').reset_index(), on=['code', 'year'], how='left')
    fq.loc[fq.q == 4, v] = fq.loc[fq.q == 4, v + '_q4']
fq['qn'] = fq.year * 4 + fq.q; fq = fq.dropna(subset=['sa', 'op']).sort_values(['code', 'qn'])
gq = fq.groupby('code')
fq['op_p'] = gq.op.shift(4).where(gq.qn.shift(4) == fq.qn - 4); fq['sa_p'] = gq.sa.shift(4).where(gq.qn.shift(4) == fq.qn - 4)
fq['d_op'] = fq.op - fq.op_p; fq['d_sa'] = fq.sa - fq.sa_p
gq = fq.groupby('code')
fq['drift'] = gq.d_op.transform(lambda s: s.shift(1).rolling(8, min_periods=4).mean())
fq['sd'] = gq.d_op.transform(lambda s: s.shift(1).rolling(8, min_periods=4).std())
fq['sue'] = (fq.d_op - fq.drift) / fq.sd
fq['rsd'] = gq.d_sa.transform(lambda s: s.shift(1).rolling(8, min_periods=4).std())
fq['rdr'] = gq.d_sa.transform(lambda s: s.shift(1).rolling(8, min_periods=4).mean())
fq['revsup'] = (fq.d_sa - fq.rdr) / fq.rsd
inc = (fq.op > fq.op_p).astype(int)
fq['streak'] = inc.groupby(fq.code).transform(lambda s: s.groupby((s != s.shift()).cumsum()).cumcount() + 1) * inc
fq['streak'] = fq.streak.clip(upper=8)
fq['t'] = np.searchsorted(dates, fq.avail.values); fq['j'] = fq.code.map(ci); fq = fq.dropna(subset=['j']); fq['j'] = fq.j.astype(int)
fq = fq[fq.t < T]
def ffq(col):
    A = np.full((T, N), np.nan); A[fq.t.values, fq.j.values] = fq[col].values
    return D(A).ffill(limit=100).values

SPLIT = 20230630; HZ = 20
F20 = np.vstack([C[HZ:] / C[:-HZ] - 1, np.full((HZ, N), np.nan)]) * 100
KX = np.r_[(bench[HZ:] / bench[:-HZ] - 1) * 100, np.full(HZ, np.nan)]
rows = []
def ev(name, X, sign, note=''):
    X = X * sign
    out = []
    for off in (0, 10):
        for t in range(260 + off, T - HZ, 20):
            m = LIQ[t] & np.isfinite(X[t]) & np.isfinite(F20[t])
            if m.sum() < 150: continue
            x = X[t, m]
            if np.unique(x).size < 15: continue
            q = x >= np.quantile(x, .9)
            if q.mean() > .3: continue
            r = F20[t, m]; out.append((off, t, r[q].mean() - r.mean(), r[q].mean() - KX[t], q.sum()))
    if len(out) < 20:
        print(name, '표본 부족', len(out)); return
    a = pd.DataFrame(out, columns=['off', 't', 'ex', 'kx', 'n'])
    a0 = a[a.off == 0].sort_values('t'); x = a0.ex.values; n = len(x); k = n // 3; s = np.sort(x)[::-1]
    tr = a[dates[a.t] <= SPLIT]; te = a[dates[a.t] > SPLIT]
    te0 = te[te.off == 0].ex.values
    rows.append(dict(신호=name, 부호=('+' if sign > 0 else '−'), 시작=int(dates[a.t.min()]), 회차=n, 종목=round(a.n.mean()),
                     초과=x.mean(), t=x.mean() / nw_se(x, 0), 중앙=np.median(x), fold=f'{x[:k].mean():.2f}/{x[k:2*k].mean():.2f}/{x[2*k:].mean():.2f}',
                     앞=tr.ex.mean(), 뒤=te.ex.mean(), 뒤_t=(te0.mean() / nw_se(te0, 0)) if len(te0) > 5 else np.nan,
                     오프셋10=a[a.off == 10].ex.mean(), 상위5pct제거=s[max(2, int(n * .05)):].mean(), KODEX대비=a.kx.mean(), 비고=note))
    print(name, round(x.mean(), 3), round(x.mean() / nw_se(x, 0), 2), flush=True)

with np.errstate(invalid='ignore', divide='ignore'):
    # ---------- 가격 ----------
    cov = D(R).rolling(21, min_periods=15).cov(D(M)).values; vm = D(M).rolling(21, min_periods=15).var().values
    b21 = cov / vm; resid = R - b21 * M
    ev('IdioVol (1개월 잔차σ, 시장 1요인)', D(resid).rolling(21, min_periods=15).std().values, -1, 'FF3 대신 시장 1요인'); del cov, vm, b21, resid; gc.collect()
    ev('MaxRet (1개월 최대 일수익)', D(R).rolling(21, min_periods=15).max().values, -1)
    ev('ReturnSkew (1개월 일수익 왜도)', D(R).rolling(21, min_periods=15).skew().values, -1)
    cov = D(R).rolling(252, min_periods=120).cov(D(M)).values; vm = D(M).rolling(252, min_periods=120).var().values
    ev('Beta (252일 일별)', cov / vm, +1, '원문 60개월 월별'); ev('저베타 (BAB 방향)', cov / vm, -1, 'Frazzini-Pedersen 방향 대조'); del cov, vm; gc.collect()
    R3 = D(R).rolling(3).sum().values; M3 = D(M).rolling(3).sum().values
    corr = D(R).rolling(504, min_periods=250).corr(D(M)).values * 0 + D(R3).rolling(504, min_periods=250).corr(D(M3)).values
    sdr = D(R).rolling(252, min_periods=120).std().values; sdm = D(M).rolling(252, min_periods=120).std().values
    ev('BetaFP (3일합 상관×σ비)', corr * sdr / sdm, +1, '원문 5년 → 2년'); del R3, M3, corr; gc.collect()
    rd = R - D(R).rolling(252, min_periods=120).mean().values; md = M - D(M).rolling(252, min_periods=120).mean().values
    ev('CoskewACX (252일)', D(rd * md ** 2).rolling(252, min_periods=120).mean().values / (sdr * sdm ** 2), -1); del rd, md, sdr, sdm; gc.collect()
    dn = np.where(M < D(M).rolling(252, min_periods=120).mean().values, 1.0, np.nan)
    ev('DownsideBeta (시장 평균 이하일)', D(R * dn).rolling(252, min_periods=60).cov(D(M * dn)).values / D(M * dn).rolling(252, min_periods=60).var().values, +1); del dn; gc.collect()
    ev('IntMom (t−12~t−6개월)', sh(C, 126) / sh(C, 252) - 1, +1)
    ev('MRreversal (t−18~t−13개월)', sh(C, 273) / sh(C, 378) - 1, -1)
    ev('LRreversal (t−36~t−13개월)', sh(C, 273) / sh(C, 756) - 1, -1)
    m21 = C / sh(C, 21) - 1
    ss = np.full((T, N), np.nan)
    for t in range(1260, T):  # 같은 달 수익(2~5년 전) 평균 — 다음 21일 창과 같은 계절
        acc = []
        for y in (2, 3, 4, 5):
            a_, b_ = t - 252 * y, t - 252 * y + 21
            acc.append(C[b_] / C[a_] - 1)
        ss[t] = np.nanmean(acc, 0)
    ev('MomSeason (2~5년 전 같은 달)', ss, +1, '2024년 이후만')
    ev('MomSeasonShort (1년 전 같은 달)', sh(C, 231) / sh(C, 252) - 1, +1); del ss; gc.collect()
    pos = np.ones((T, N))
    for k in range(6):
        pos = pos * (sh(m21, 21 * k) > 0) if k else (m21 > 0) * 1.0
    ev('ConsPosRet (6개월 연속 상승)', pos, +1); del pos
    ev('Price (낮은 주가)', np.log(C), -1)
    shrs = ff(f.shrs.values); turn = V / shrs
    mturn = D(turn).rolling(21, min_periods=15).sum().values
    ev('std_turn (월 회전율 변동, 36개월)', D(mturn[::1]).rolling(756, min_periods=300).std().values, -1, '일별 이동 근사')
    mvol = D(V).rolling(21, min_periods=15).sum().values
    ev('VolSD (월 거래량 변동, 36개월)', D(mvol).rolling(756, min_periods=500).std().values / D(mvol).rolling(756, min_periods=500).mean().values, -1, '평균으로 정규화')
    tt_ = np.arange(T, dtype=float)[:, None] * np.ones((1, N))
    ev('VolumeTrend (60개월→2년 거래량 추세)', D(mvol).rolling(504, min_periods=250).cov(D(tt_)).values / D(tt_).rolling(504, min_periods=250).var().values / D(mvol).rolling(504, min_periods=250).mean().values, -1, '창 2년'); del tt_; gc.collect()
    mom6 = sh(C, 21) / sh(C, 147) - 1; tv6 = D(turn).rolling(126, min_periods=100).mean().values
    hv = np.zeros((T, N), bool)
    for t in range(T):
        m = LIQ[t] & np.isfinite(tv6[t])
        if m.sum() > 50: hv[t] = m & (tv6[t] >= np.nanquantile(tv6[t][m], 2 / 3))
    ev('MomVol (고회전 1/3 안 6개월 모멘텀)', np.where(hv, mom6, np.nan), +1); del hv, tv6, mom6
    ev('Illiquidity (Amihud 12개월)', D(np.abs(R) / (C * V)).rolling(252, min_periods=150).mean().values, +1)
    del turn, mturn, mvol; gc.collect()
    # ---------- 재무 ----------
    mcap = shrs * C
    ev('AssetGrowth (총자산 증가율)', ff((f.ta / f.ta_y - 1).values), -1)
    ev('ChEQ (자본 증가율)', ff(np.where((f['eq'] > 0) & (f.eq_y > 0), f['eq'] / f.eq_y, np.nan)), -1)
    ev('ShareIss1Y (주식수 증가)', ff((f.shrs / f.shrs_y - 1).values), -1, '원문 t−18~t−6 → 4분기')
    ev('OperProf (영업이익/자본)', ff(np.where(f['eq'] > 0, f.op / f['eq'], np.nan)), +1, '원문 매출−원가−판관비−이자')
    ev('ROA (순이익/전년 자산)', ff((f.ni / f.ta_y).values), +1, 'roaq 근사(TTM)')
    ev('AssetTurnover (매출/총자산)', ff((f.sa / f.ta).values), +1, '분모 순영업자산 → 총자산')
    ev('ChAssetTurnover (자산회전율 변화)', ff((f.sa / f.ta - f.sa_y / f.ta_y).values), +1)
    ev('ChPM (순이익률 변화)', ff((f.ni / f.sa - f.ni_y / f.sa_y).values), +1)
    ev('Leverage (부채/시총)', ff(f.tl.values) / mcap, +1)
    ev('BookLeverage (자산/자본)', ff(np.where(f['eq'] > 0, f.ta / f['eq'], np.nan)), -1)
    ev('AM (자산/시총)', ff(f.ta.values) / mcap, +1)
    ev('EarningsSurprise (영업이익 SUE)', ffq('sue'), +1, 'EPS → 분기 영업이익')
    ev('RevenueSurprise (매출 SUE)', ffq('revsup'), +1, '주당 → 총액')
    ev('NumEarnIncrease (영업이익 YoY 증가 연속)', ffq('streak'), +1)
r = pd.DataFrame(rows).sort_values('t', ascending=False); r.to_csv('anomaly.csv', index=False)
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 40)
print(r.round(2).to_string(index=False))
