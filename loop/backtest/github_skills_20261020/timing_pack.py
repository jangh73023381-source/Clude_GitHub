"""KODEX200 타이밍 팩 — GitHub/퀀트 블로그 고전 규칙. 신호는 D 종가 확정 후, 포지션은 D 종가 진입 → D+1 종가 수익.
현금 수익 0, 비용 0(ETF·v2.8). 대조: 같은 노출 비율·같은 보유 블록 길이를 무작위 배치한 타이밍 1,000회."""
import numpy as np, pandas as pd
from gh_stats import nw_se
p = pd.read_csv('/mnt/user-data/uploads/loop/backtest/panel_ohlc_long.csv', dtype={'code': str})
k = p[p.code == '069500'].sort_values('date').reset_index(drop=True)
us = p[p.code == '133690'].set_index('date').close
O, H, L, C, V = (k[c].values.astype(float) for c in ('open', 'high', 'low', 'close', 'volume')); dates = k.date.values; T = len(C)
r_next = np.r_[C[1:] / C[:-1] - 1, np.nan]
s = pd.Series(C)
ma200, ma5 = s.rolling(200).mean().values, s.rolling(5).mean().values
def rsi(x, n):
    d = np.diff(x, prepend=np.nan); u = pd.Series(np.where(d > 0, d, 0.)).ewm(alpha=1 / n, adjust=False).mean()
    w = pd.Series(np.where(d < 0, -d, 0.)).ewm(alpha=1 / n, adjust=False).mean(); return (100 - 100 / (1 + u / w)).values
rsi2 = rsi(C, 2); ibs = (C - L) / (H - L + 1e-12)
lo7 = s.rolling(7).min().values; hi7 = s.rolling(7).max().values
def statefull(entry, exit_):
    pos = np.zeros(T); h = 0
    for t in range(T):
        if h == 0 and entry[t]: h = 1
        elif h == 1 and exit_[t]: h = 0
        pos[t] = h
    return pos
S = {}
S['IBS<0.2 매수 → IBS>0.8 매도'] = statefull(ibs < .2, ibs > .8)
S['Double 7s (MA200 위·7일 최저 종가 → 7일 최고)'] = statefull((C > ma200) & (C <= lo7), C >= hi7)
S['Connors RSI2 (MA200 위·RSI2<10 → 종가>MA5)'] = statefull((C > ma200) & (rsi2 < 10), C > ma5)
# IBD 분배일 / FTD (tradermonty ibd-distribution-day-monitor · ftd-detector 정의)
chg = np.r_[np.nan, C[1:] / C[:-1] - 1]; vup = np.r_[False, V[1:] > V[:-1]]
dist = (chg <= -0.002) & vup
cnt = pd.Series(dist.astype(float)).rolling(25).sum().values
for thr in (5, 6):
    pos = np.zeros(T); h = 1; low = np.inf; day = 0
    for t in range(1, T):
        if h == 1 and cnt[t] >= thr:
            h = 0; low = C[t]; day = 0
        elif h == 0:
            if C[t] < low: low = C[t]; day = 0
            elif chg[t] > 0 and day == 0: day = 1
            elif day >= 1: day += 1
            if day >= 4 and chg[t] >= 0.0125 and vup[t]: h = 1
        pos[t] = h
    S[f'IBD 분배일 {thr}회/25일 → 현금, FTD 재진입'] = pos
# GEM 듀얼 모멘텀 (월말, 12개월 수익: KODEX200 vs TIGER 미국나스닥100, 절대모멘텀 기준 0)
usv = pd.Series(dates).map(us).values
pos_k = np.zeros(T); pos_u = np.zeros(T); hk = hu = 0
for t in range(252, T):
    if t + 1 < T and str(dates[t + 1])[4:6] != str(dates[t])[4:6]:
        rk = C[t] / C[t - 252] - 1; ru = usv[t] / usv[t - 252] - 1 if np.isfinite(usv[t - 252]) else -9
        hk, hu = (1, 0) if (rk >= ru and rk > 0) else ((0, 1) if (ru > rk and ru > 0) else (0, 0))
    pos_k[t], pos_u[t] = hk, hu
usr = np.r_[usv[1:] / usv[:-1] - 1, np.nan]
gem = np.nan_to_num(pos_k * r_next) + np.nan_to_num(pos_u * usr)
start = 252; end = T - 1
bh = r_next[start:end]
def perf(r):
    eq = np.cumprod(1 + r); y = len(r) / 245
    return (eq[-1] ** (1 / y) - 1) * 100, (eq / np.maximum.accumulate(eq) - 1).min() * 100, r.mean() / r.std() * np.sqrt(245) if r.std() > 0 else 0
rng = np.random.default_rng(5)
def rand_timing(pos):
    """같은 보유 블록 길이를 무작위 위치에 재배치."""
    blocks = []; t = 0
    while t < len(pos):
        u = t
        while u < len(pos) and pos[u] == pos[t]: u += 1
        blocks.append((pos[t], u - t)); t = u
    ins = [b for b in blocks if b[0] == 1]; outs = [b for b in blocks if b[0] == 0]
    rng.shuffle(ins); rng.shuffle(outs)
    seq = []; a = list(ins); b = list(outs)
    first = blocks[0][0]
    while a or b:
        for src in ((a, b) if first == 1 else (b, a)):
            if src: v, l = src.pop(); seq += [v] * l
    return np.array(seq[:len(pos)])
rows = []
cg, md, sh = perf(bh); rows.append(dict(규칙='KODEX200 보유(B&H)', CAGR=cg, MDD=md, Sharpe=sh, 노출=100.0))
for nm, pos in list(S.items()) + [('GEM 듀얼모멘텀 (KODEX200 vs 미국나스닥100, 월1회)', None)]:
    if pos is None:
        r = gem[start:end]; expo = (pos_k + pos_u)[start:end].mean() * 100; pp = None
    else:
        pp = pos[start:end]; r = np.nan_to_num(pp * bh); expo = pp.mean() * 100
    cg, md, sh = perf(r); n = len(r); k3 = n // 3
    row = dict(규칙=nm, CAGR=cg, MDD=md, Sharpe=sh, 노출=expo, 거래수=int(np.sum(np.diff(pp) == 1)) if pp is not None else None,
               fold_Sharpe='/'.join(f'{perf(r[i*k3:(i+1)*k3])[2]:.2f}' for i in range(3)))
    if pp is not None:
        sims = np.array([perf(np.nan_to_num(rand_timing(pp) * bh))[2] for _ in range(1000)])
        row['무작위타이밍_Sharpe중앙'] = np.median(sims); row['p'] = (sims >= sh).mean()
        inr = bh[pp == 1]; row['보유일_평균수익'] = inr.mean() * 100; row['전체일_평균'] = bh.mean() * 100
    rows.append(row)
o = pd.DataFrame(rows); pd.set_option('display.width', 260); pd.set_option('display.max_columns', 20)
print('기간', dates[start], '~', dates[end - 1]); print(o.round(3).to_string(index=False)); o.to_csv('timing_pack.csv', index=False)
