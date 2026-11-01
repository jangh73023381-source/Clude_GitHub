"""2026-10-27 GitHub 미검정 규칙형 스킬 — SKILL.md 설명을 읽고 직접 구현(저장소 코드 미실행).
A. 개별주 이벤트(7.7년 dense, 유동 종목): Vibe-Trading ichimoku·candlestick(15종)·smc·volatility, tradermonty stockbee-20pct-study
   지표 = 신호 종목 D→D+h 수익 − 같은 날 유동 평균(%), 신호일별 평균 → NW t(lag h-1), 3분할, 앞/뒤(2023-06-30), 상위 5% 신호일 제거.
B. finskills quant-factor-screener 6팩터 합성(가치·모멘텀·품질·저변동·소형·성장, 동일가중 백분위) — 분기 리밸런싱 패널.
C. KODEX200 타이밍: tradermonty market-breadth-analyzer(폭 8MA vs 200MA)·uptrend-analyzer(상승추세 비율), Vibe-Trading seasonal."""
import numpy as np, pandas as pd, pickle
from gh_stats import nw_se, summarize
Z = np.load('dense.npz'); dates = Z['dates'].astype(int); O, H, L, C, V = (Z[k].astype(float) for k in 'OHLCV'); bench = Z['bench'].astype(float)
T, N = C.shape
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
SPLIT = 20230630
D = lambda A: pd.DataFrame(A)
sh = lambda A, d: np.vstack([np.full((d, N), np.nan), A[:-d]])
fwd = {h: np.vstack([C[h:] / C[:-h] - 1, np.full((h, N), np.nan)]) * 100 for h in (1, 5, 20)}
kfw = {h: np.r_[(bench[h:] / bench[:-h] - 1) * 100, np.full(h, np.nan)] for h in (1, 5, 20)}
R = []


def event(name, sig, hs=(5, 20)):
    sig = sig & LIQ
    sig[:260] = False
    for h in hs:
        F = fwd[h]; um = np.nanmean(np.where(LIQ & np.isfinite(F), F, np.nan), 1)
        t, j = np.where(sig & np.isfinite(F))
        if len(t) < 200: continue
        ex = F[t, j] - um[t]; kx = F[t, j] - kfw[h][t]
        o = summarize(f'{name} | {h}일', t, ex, h - 1, {'종목/일': round(len(t) / len(np.unique(t)), 1)})
        dd = pd.DataFrame({'t': t, 'ex': ex, 'kx': kx}).groupby('t').mean()
        tr, te = dd[dates[dd.index] <= SPLIT], dd[dates[dd.index] > SPLIT]
        o.update(앞=tr.ex.mean(), 뒤=te.ex.mean(), 뒤_t=te.ex.mean() / nw_se(te.ex.values, h - 1), KODEX대비=dd.kx.mean(), 뒤_KODEX대비=te.kx.mean())
        R.append(o)


with np.errstate(all='ignore'):
    # ---- Ichimoku: 전환(9) 기준(26) 골든크로스 + 구름 위 + 양운(선행A>B). 구름은 26일 앞으로 그린 값 → 오늘 구름 = 26일 전 계산값
    hh = lambda n: D(H).rolling(n).max().values; ll = lambda n: D(L).rolling(n).min().values
    tenkan = (hh(9) + ll(9)) / 2; kijun = (hh(26) + ll(26)) / 2
    spanA = sh((tenkan + kijun) / 2, 26); spanB = sh((hh(52) + ll(52)) / 2, 26)
    tk_up = (tenkan > kijun) & (sh(tenkan, 1) <= sh(kijun, 1))
    event('Ichimoku 강한매수(TK골든+구름위+양운)', tk_up & (C > np.fmax(spanA, spanB)) & (spanA > spanB))
    event('Ichimoku TK골든크로스 단독', tk_up.copy())
    # ---- Candlestick 15종 점수(강세 +1 / 약세 −1), 점수>0 매수
    body = np.abs(C - O); rng = H - L + 1e-9; up = H - np.fmax(O, C); lo = np.fmin(O, C) - L
    ma10 = D(C).rolling(10).mean().values; downtr = C < ma10; uptr = C > ma10
    pO, pC, pH, pL = sh(O, 1), sh(C, 1), sh(H, 1), sh(L, 1); ppO, ppC = sh(O, 2), sh(C, 2)
    pbody = np.abs(pC - pO); ppbody = np.abs(ppC - ppO)
    bull = np.zeros((T, N)); bear = np.zeros((T, N))
    small = body <= rng * .3
    bull += (small & (lo >= 2 * body) & (up <= body) & downtr)                          # Hammer
    bull += (small & (up >= 2 * body) & (lo <= body) & downtr)                          # Inverted hammer
    bear += (small & (up >= 2 * body) & (lo <= body) & uptr)                            # Shooting star
    bear += (small & (lo >= 2 * body) & (up <= body) & uptr)                            # Hanging man
    doji = body <= rng * .1
    bull += (doji & (lo >= rng * .6) & downtr); bear += (doji & (up >= rng * .6) & uptr)  # Dragonfly / Gravestone
    bull += ((pC < pO) & (C > O) & (O <= pC) & (C >= pO) & (body > pbody))             # Bullish engulfing
    bear += ((pC > pO) & (C < O) & (O >= pC) & (C <= pO) & (body > pbody))             # Bearish engulfing
    bull += ((pC < pO) & (C > O) & (O < pL) & (C > (pO + pC) / 2) & (C < pO))          # Piercing
    bear += ((pC > pO) & (C < O) & (O > pH) & (C < (pO + pC) / 2) & (C > pO))          # Dark cloud
    bull += ((pC < pO) & (C > O) & (O > pC) & (C < pO) & (body < pbody * .5))          # Bullish harami
    bear += ((pC > pO) & (C < O) & (O < pC) & (C > pO) & (body < pbody * .5))          # Bearish harami
    bull += ((ppC < ppO) & (pbody < ppbody * .3) & (C > O) & (C > (ppO + ppC) / 2))   # Morning star
    bear += ((ppC > ppO) & (pbody < ppbody * .3) & (C < O) & (C < (ppO + ppC) / 2))   # Evening star
    w3 = (C > O) & (pC > pO) & (ppC > ppO) & (C > pC) & (pC > ppC)
    bull += w3                                                                          # Three white soldiers
    b3 = (C < O) & (pC < pO) & (ppC < ppO) & (C < pC) & (pC < ppC)
    bear += b3                                                                          # Three black crows
    score = bull - bear
    event('Candlestick 15종 점수>0', score > 0)
    event('Candlestick 15종 점수>=2', score >= 2)
    # ---- SMC: 5봉 프랙털 스윙고점(확정은 2봉 뒤) 상향 돌파(BOS/ChoCH) + 최근 5일 내 강세 FVG(L[t] > H[t-2])
    frac = (sh(H, 2) > sh(H, 3)) & (sh(H, 2) > sh(H, 4)) & (sh(H, 2) > sh(H, 1)) & (sh(H, 2) > H)
    swing = D(np.where(frac, sh(H, 2), np.nan)).ffill().values
    bos = (C > swing) & (sh(C, 1) <= sh(swing, 1))
    fvg = L > sh(H, 2); fvg5 = D(fvg.astype(float)).rolling(5).max().values > 0
    event('SMC 구조돌파+강세FVG', bos & fvg5)
    # ---- Volatility 국면: σ20 의 자기 250일 백분위 < 20% (수축 → 확장 대기)
    r1 = C / sh(C, 1) - 1; s20 = D(r1).rolling(20, min_periods=15).std().values
    pct = D(s20).rolling(250, min_periods=200).rank(pct=True).values
    event('Volatility 국면 σ20 백분위<20%', pct < .2)
    # ---- Stockbee 20% 급등(5일 내 +20%, 첫날) 이후 추종
    r5 = C / sh(C, 5) - 1
    first = (r5 >= .2) & ~(sh(r5, 1) >= .2)
    event('Stockbee +20%(5일) 첫날 → 추종', first)
    event('Stockbee −20%(5일) 첫날 → 반등', (r5 <= -.2) & ~(sh(r5, 1) <= -.2))

ev = pd.DataFrame(R)
# ================= B. finskills quant-factor-screener =================
f = pd.read_pickle('gh_fund_panel.pkl')
t_, j_ = f.t.values.astype(int), f.j.values.astype(int)
with np.errstate(all='ignore'):
    mom = C[np.maximum(t_ - 21, 0), j_] / C[np.maximum(t_ - 252, 0), j_] - 1
    lr = np.log(C / sh(C, 1)); kr = np.r_[np.nan, np.log(bench[1:] / bench[:-1])]
    vol1y = np.array([np.nanstd(lr[max(t - 250, 1):t + 1, j]) for t, j in zip(t_, j_)])
    dn = np.where(lr < 0, lr, 0.)
    down = np.array([np.sqrt(np.nanmean(dn[max(t - 250, 1):t + 1, j] ** 2)) for t, j in zip(t_, j_)])
    def beta(t, j):
        a = lr[max(t - 500, 1):t + 1, j]; b = kr[max(t - 500, 1):t + 1]; m = np.isfinite(a) & np.isfinite(b)
        return np.cov(a[m], b[m])[0, 1] / np.var(b[m]) if m.sum() > 100 else np.nan
    bet = np.array([beta(t, j) for t, j in zip(t_, j_)])
f['mom'] = mom; f['vol1y'] = vol1y; f['down'] = down; f['beta'] = bet
f['bp'] = 1 / f.pbr; f['fin'] = 1 - f.tl / f.ta; f['opmd'] = f.opm - f.opm_p
g = f.groupby('rb')
P = lambda c, asc=True: g[c].rank(pct=True, ascending=asc)
f['F_value'] = (0.6 * P('ey') + 0.4 * P('bp'))
f['F_mom'] = P('mom')
f['F_quality'] = (0.55 * P('roe') + 0.45 * P('fin'))
f['F_lowvol'] = (0.4 * P('vol1y', False) + 0.3 * P('beta', False) + 0.3 * P('down', False))
f['F_size'] = P('mktcap', False)
f['F_growth'] = (0.6 * P('sag') + 0.4 * P('opmd'))
facs = ['F_value', 'F_mom', 'F_quality', 'F_lowvol', 'F_size', 'F_growth']
f['comp6'] = f[facs].mean(1, skipna=False); f['comp5'] = f[[x for x in facs if x != 'F_size']].mean(1, skipna=False)
RB = []
for h in (60, 20):
    um = f.groupby('t')[f'r{h}'].mean()
    for nm, col in [('6팩터 합성(원안, 동일가중)', 'comp6'), ('5팩터(소형 제외)', 'comp5')] + [(c, c) for c in facs]:
        x = f[f[col].notna() & f[f'r{h}'].notna()]
        top = x[x.groupby('rb')[col].rank(pct=True) >= .9]
        ex = top[f'r{h}'].values - um.reindex(top.t).values
        dd = pd.DataFrame({'t': top.t.values, 'ex': ex, 'kx': (top[f'r{h}'] - top[f'k{h}']).values}).groupby('t').mean()
        o = summarize(f'finskills {nm} 상위10% | {h}일', top.t.values, ex, 0, {'종목/회': round(len(top) / top.t.nunique(), 1)})
        o.update(앞=dd[dates[dd.index] <= SPLIT].ex.mean(), 뒤=dd[dates[dd.index] > SPLIT].ex.mean(), KODEX대비=dd.kx.mean(),
                 뒤_KODEX대비=dd[dates[dd.index] > SPLIT].kx.mean())
        RB.append(o)
fb = pd.DataFrame(RB)
# ================= C. KODEX200 타이밍 =================
ma200 = D(C).rolling(200).mean().values; ma50 = D(C).rolling(50).mean().values
okb = LIQ & np.isfinite(ma200)
br = np.nansum(okb & (C > ma200), 1) / np.maximum(okb.sum(1), 1) * 100            # % 종목 > MA200
upt = np.nansum(okb & (C > ma50) & (ma50 > ma200), 1) / np.maximum(okb.sum(1), 1) * 100  # 상승추세 비율
b8 = pd.Series(br).rolling(8).mean().values; b200 = pd.Series(br).rolling(200).mean().values
u10 = pd.Series(upt).rolling(10).mean().values
rk = kfw[1] / 100
rng = np.random.default_rng(7)


def rand_timing(pos):
    blocks = []; t = 0
    while t < len(pos):
        u = t
        while u < len(pos) and pos[u] == pos[t]: u += 1
        blocks.append((pos[t], u - t)); t = u
    ins = [b for b in blocks if b[0] == 1]; outs = [b for b in blocks if b[0] == 0]
    rng.shuffle(ins); rng.shuffle(outs); seq = []; a, b = list(ins), list(outs); first = blocks[0][0]
    while a or b:
        for src in ((a, b) if first == 1 else (b, a)):
            if src: v, l = src.pop(); seq += [v] * l
    return np.array(seq[:len(pos)])


def perf(r):
    eq = np.cumprod(1 + r); y = len(r) / 245
    return (eq[-1] ** (1 / y) - 1) * 100, (eq / np.maximum.accumulate(eq) - 1).min() * 100, r.mean() / r.std() * np.sqrt(245) if r.std() > 0 else 0


s0 = 470; s1 = T - 1; bh = np.nan_to_num(rk[s0:s1])
month = (dates // 100) % 100
TM = {'market-breadth: 폭 8MA > 폭 200MA': (b8 > b200), 'market-breadth: 폭(>MA200) ≥ 50%': br >= 50,
      'uptrend-analyzer: 상승추세비율 ≥ 10일평균': upt >= u10, 'seasonal: 11~4월 보유(Sell in May)': np.isin(month, [11, 12, 1, 2, 3, 4])}
RC = [dict(규칙='KODEX200 보유', CAGR=perf(bh)[0], MDD=perf(bh)[1], Sharpe=perf(bh)[2], 노출=100.0)]
for nm, m in TM.items():
    pos = m[s0:s1].astype(float); r = pos * bh; cg, md, s_ = perf(r); n = len(r); k3 = n // 3
    sims = np.array([perf(rand_timing(pos) * bh)[2] for _ in range(500)])
    RC.append(dict(규칙=nm, CAGR=cg, MDD=md, Sharpe=s_, 노출=pos.mean() * 100, 무작위Sharpe중앙=np.median(sims), p=(sims >= s_).mean(),
                   fold_Sharpe='/'.join(f'{perf(r[i*k3:(i+1)*k3])[2]:.2f}' for i in range(3))))
tc = pd.DataFrame(RC)
pd.set_option('display.width', 320); pd.set_option('display.max_columns', 30)
print('A. 개별주 이벤트', dates[260], '~', dates[-21]); print(ev.round(3).to_string(index=False))
print('\nB. finskills 6팩터 (분기)', f.rb.nunique(), '회'); print(fb.round(3).to_string(index=False))
print('\nC. KODEX200 타이밍', dates[s0], '~', dates[s1 - 1]); print(tc.round(3).to_string(index=False))
ev.to_csv('rule_events.csv', index=False); fb.to_csv('rule_finskills.csv', index=False); tc.to_csv('rule_timing.csv', index=False)
