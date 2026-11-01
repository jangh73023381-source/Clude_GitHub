"""GitHub 가격 전략 8종 — 개별종목 7.7년(dense.npz). 진입 = 신호일 종가.
평가 ① 20거래일 고정 ② 원 규칙 청산(상한 60일). 기준 = 같은 날 유동 유니버스 동일가중(같은 보유 구간)."""
import numpy as np, pandas as pd, pickle
Z = np.load('dense.npz'); dates = Z['dates']; O, H, L, C, V = (Z[k] for k in 'OHLCV'); T, N = C.shape
cs = np.cumsum(np.nan_to_num(C * V), 0); val20 = np.full((T, N), np.nan); val20[20:] = (cs[20:] - cs[:-20]) / 20
LIQ = (C >= 1000) & (val20 >= 1e9)
sh = lambda A, k=1: np.vstack([np.full((k, N), np.nan), A[:-k]])
DF = lambda A: pd.DataFrame(A)
def sma(A, n): return DF(A).rolling(n, min_periods=n).mean().values
def ema(A, n): return DF(A).ewm(span=n, adjust=False, min_periods=n).mean().values
def rsi(A, n, wilder=True):
    d = np.diff(A, axis=0, prepend=np.nan); up = np.where(d > 0, d, 0.); dn = np.where(d < 0, -d, 0.)
    up[np.isnan(d)] = np.nan; dn[np.isnan(d)] = np.nan
    a = (lambda X: DF(X).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().values) if wilder else (lambda X: sma(X, n))
    ru, rd = a(up), a(dn)
    with np.errstate(divide='ignore', invalid='ignore'):
        return 100 - 100 / (1 + ru / rd)

S = {}  # name -> (entry bool, exit bool, cap)
with np.errstate(invalid='ignore'):
    # P1 MACD oscillator (je-suis-tm: SMA 12/26 교차)
    m1, m2 = sma(C, 12), sma(C, 26); pos = m1 >= m2
    S['MACD 오실레이터(SMA12/26 골든크로스)'] = (pos & ~sh(pos.astype(float)).astype(bool) & ~np.isnan(m2), ~pos & ~np.isnan(m2), 60)
    # P2 Parabolic SAR (0.02/0.02/0.2) — 시간축 루프, 종목 벡터화
    trend = np.zeros((T, N)); sar = np.full((T, N), np.nan); ep = np.full(N, np.nan); af = np.full(N, 0.02)
    tr = np.where(C[1] > C[0], 1, -1).astype(float); s = np.where(tr > 0, L[0], H[0]); ep = np.where(tr > 0, H[1], L[1])
    for i in range(2, T):
        hi, lo = H[i], L[i]
        ini = np.isnan(s) & ~np.isnan(hi) & ~np.isnan(L[i-1]) & ~np.isnan(L[i-2])
        s = np.where(ini, np.fmin(L[i-1], L[i-2]), s); ep = np.where(ini, H[i-1], ep); tr = np.where(ini, 1, tr); af = np.where(ini, 0.02, af)
        s = s + af * (ep - s)
        s = np.where(tr > 0, np.fmin(s, np.fmin(L[i-1], L[i-2])), np.fmax(s, np.fmax(H[i-1], H[i-2])))
        flip_dn = (tr > 0) & (lo < s); flip_up = (tr < 0) & (hi > s)
        new_ep = np.where(tr > 0, np.fmax(ep, hi), np.fmin(ep, lo))
        af = np.where(new_ep != ep, np.minimum(af + 0.02, 0.2), af)
        ep = new_ep
        s = np.where(flip_dn, ep, np.where(flip_up, ep, s))
        ep = np.where(flip_dn, lo, np.where(flip_up, hi, ep))
        af = np.where(flip_dn | flip_up, 0.02, af)
        tr = np.where(flip_dn, -1, np.where(flip_up, 1, tr))
        bad = np.isnan(hi) | np.isnan(s)
        tr = np.where(np.isnan(tr), 1, tr); trend[i] = np.where(bad, 0, tr)
    S['Parabolic SAR 상승 전환'] = ((trend == 1) & (sh(trend) == -1), trend == -1, 60)
    # P3 Heikin-Ashi (je-suis-tm: 위꼬리 없는 장대 음봉 2연속 → 매수, 아래꼬리 없는 양봉 2연속 → 청산)
    hc = (O + H + L + C) / 4; ho = np.full((T, N), np.nan); ho[0] = (O[0] + C[0]) / 2
    for i in range(1, T):
        ho[i] = np.where(np.isnan(ho[i-1]), (O[i] + C[i]) / 2, (ho[i-1] + hc[i-1]) / 2)
    hh = np.fmax(np.fmax(H, ho), hc); hl = np.fmin(np.fmin(L, ho), hc)
    bear = ho > hc; body = np.abs(ho - hc)
    ent = bear & np.isclose(ho, hh) & (body > sh(body)) & sh(bear.astype(float)).astype(bool)
    ext = (ho < hc) & np.isclose(ho, hl) & sh((ho < hc).astype(float)).astype(bool)
    S['Heikin-Ashi 역추세'] = (ent, ext, 60)
    # P4 Awesome Oscillator saucer
    mp = (H + L) / 2; ao = sma(mp, 5) - sma(mp, 34)
    ent = (O > C) & (sh(O) < sh(C)) & (sh(O, 2) < sh(C, 2)) & (sh(ao) > sh(ao, 2)) & (sh(ao) < 0) & (ao < 0)
    ext = (O < C) & (sh(O) > sh(C)) & (sh(O, 2) > sh(C, 2)) & (sh(ao) < sh(ao, 2)) & (sh(ao) > 0) & (ao > 0)
    S['Awesome Oscillator 소서'] = (ent, ext, 60)
    # P5 RSI14 <30 매수, >70 청산 (je-suis-tm)
    r14 = rsi(C, 14, wilder=False)
    S['RSI14 과매도(<30)'] = ((r14 < 30) & (sh(r14) >= 30), r14 > 70, 60)
    # P6 Connors RSI(2)
    r2 = rsi(C, 2); m200, m5 = sma(C, 200), sma(C, 5)
    S['Connors RSI2 (MA200 위·RSI2<10)'] = ((C > m200) & (r2 < 10), C > m5, 20)
    # P7 Turtle System 2 (55일 돌파 → 20일 저점 이탈)
    h55 = sh(DF(H).rolling(55).max().values); l20 = sh(DF(L).rolling(20).min().values)
    br = C > h55
    S['Turtle 55일 돌파'] = (br & ~sh(br.astype(float)).astype(bool), C < l20, 60)
    h20 = sh(DF(H).rolling(20).max().values); l10 = sh(DF(L).rolling(10).min().values); b1 = C > h20
    S['Turtle 20일 돌파(System1)'] = (b1 & ~sh(b1.astype(float)).astype(bool), C < l10, 60)

# 12-1 모멘텀 (월 1회, 유동 유니버스 상위 10%)
mom = sh(C, 21) / sh(C, 252) - 1
ent = np.zeros((T, N), bool)
for t in range(260, T, 20):
    m = LIQ[t] & ~np.isnan(mom[t]); v = np.where(m, mom[t], np.nan)
    if m.sum() > 50: ent[t] = v >= np.nanpercentile(v, 90)
S['12-1 모멘텀 상위10%(월1회)'] = (ent, np.zeros((T, N), bool), 20)

# --- 평가 ---
def next_exit(ex, cap):
    """각 (t,j)에서 t 이후 첫 exit 인덱스(상한 t+cap)."""
    nx = np.full((T, N), T, dtype=np.int32); cur = np.full(N, T, dtype=np.int32)
    for t in range(T - 1, -1, -1):
        nx[t] = cur; cur = np.where(ex[t], t, cur)
    return np.minimum(nx, np.arange(T)[:, None] + cap)

U = np.where(LIQ, C, np.nan)
def uni_ret(t0, t1):
    a, b = C[t0], C[t1]; m = LIQ[t0] & ~np.isnan(b) & ~np.isnan(a)
    return np.nanmean(b[m] / a[m] - 1) * 100

OUT = {}
for name, (ent, ext, cap) in S.items():
    ent = ent & LIQ; ent[:260] = False
    nx = next_exit(ext, cap)
    tt, jj = np.where(ent[:T - 21]); recs = []
    ucache = {}
    for t, j in zip(tt, jj):
        e = min(nx[t, j], T - 1)
        if np.isnan(C[t + 20, j]) or np.isnan(C[e, j]): continue
        r20 = (C[t + 20, j] / C[t, j] - 1) * 100; rr = (C[e, j] / C[t, j] - 1) * 100
        k = (t, 20); ucache.setdefault(k, uni_ret(t, t + 20)); k2 = (t, e); ucache.setdefault(k2, uni_ret(t, e))
        recs.append((t, j, r20, r20 - ucache[k], rr, rr - ucache[k2], e - t))
    OUT[name] = np.array(recs)
    print(name, len(recs), flush=True)
pickle.dump(OUT, open('gh_price.pkl', 'wb'))
