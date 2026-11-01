#!/usr/bin/env python3
"""Sell-Ban 검정 엔진 (2026-09-11, 조회 전용).

질문: 어떤 '매도 신호'가 뜬 ETF 는 이후 H 거래일 동안 유니버스보다 못한가? (못하면 그 기간 매수 금지)
진입 기준: 신호일 D 종가로 신호 확정 → 브리핑일 T=D+1 종가에 샀다고 가정(트랙 D 집행과 동일) →
          R_H = C[D+1+H] / C[D+1] - 1. 비교 기준 = 같은 창의 유니버스 동일가중 평균(날짜 매칭 → 시장 국면 제거).
X_H = R_H - 유니버스평균. **음수일수록 좋은 매도(회피) 신호.**
"""
import os, pickle
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    return pickle.load(open(os.path.join(HERE, '_sb_cache.pkl'), 'rb'))


def T(x):   # (M,N) -> DataFrame(N,M) for rolling on time axis
    return pd.DataFrame(x.T)


def rmean(x, w):
    return T(x).rolling(w, min_periods=w).mean().values.T


def rmin(x, w):
    return T(x).rolling(w, min_periods=w).min().values.T


def rmax(x, w):
    return T(x).rolling(w, min_periods=w).max().values.T


def sh(x, k):
    y = np.full_like(x, np.nan, dtype=float)
    if k > 0:
        y[:, k:] = x[:, :-k]
    elif k < 0:
        y[:, :k] = x[:, -k:]
    else:
        y = x.astype(float).copy()
    return y


def rsi(C, n=14):
    d = T(C).diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return (100 - 100 / (1 + up / dn)).values.T


def xrank(x):
    """날짜별 횡단면 백분위(0~1, NaN 유지)."""
    return pd.DataFrame(x).rank(axis=0, pct=True).values


def indicators(d):
    O, H, L, C, V = d['O'], d['H'], d['L'], d['C'], d['V']
    I = dict(O=O, H=H, L=L, C=C, V=V)
    for w in (5, 10, 20, 60):
        I[f'MA{w}'] = rmean(C, w)
    I['VA'] = rmean(V, 20)
    I['RET1'] = C / sh(C, 1) - 1
    I['MOM20'] = C / sh(C, 20) - 1
    I['RSI'] = rsi(C)
    return I


def fwd(C, H, entry_lag=1):
    """R_H[m,t] = C[t+lag+H]/C[t+lag]-1 과 날짜별 유니버스 평균 차 X_H."""
    e = sh(C, -entry_lag); x = sh(C, -(entry_lag + H))
    R = x / e - 1
    mu = np.nanmean(np.where(np.isnan(R), np.nan, R), axis=0)
    return R, R - mu[None, :]


def nw_t(y, L):
    y = np.asarray(y, float); n = len(y)
    if n < 10:
        return np.nan
    e = y - y.mean(); v = e @ e / n
    for l in range(1, min(L, n - 1) + 1):
        v += 2 * (1 - l / (L + 1)) * (e[l:] @ e[:-l]) / n
    return y.mean() / np.sqrt(v / n) if v > 0 else np.nan


def stats(S, X, H, R=None, FE=None, XQ=None, N=None):
    """S: bool (M,N) 신호, X: 초과수익 행렬. 반환 dict."""
    ok = S & ~np.isnan(X)
    m, t = np.where(ok)
    if len(t) < 30:
        return dict(n=len(t))
    x = X[m, t]
    ts = np.unique(t)
    dm = pd.Series(x).groupby(t).mean()          # 날짜별 평균(정렬된 t)
    y = dm.values
    N = N or X.shape[1]
    folds = [x[(t >= a) & (t < b)].mean() if ((t >= a) & (t < b)).any() else np.nan
             for a, b in [(0, N // 3), (N // 3, 2 * N // 3), (2 * N // 3, N)]]
    srt = np.sort(y)                             # 가장 유리한(가장 음수) 날부터
    r5 = {k: (srt[k:].mean() if len(srt) > k else np.nan) for k in (1, 3, 5, 10)}
    out = dict(n=len(t), ndates=len(ts), mean=x.mean(), med=np.median(x), neg=(x < 0).mean() * 100,
               dmean=y.mean(), dmed=np.median(y), t=nw_t(y, H),
               f1=folds[0], f2=folds[1], f3=folds[2],
               r5_1=r5[1], r5_3=r5[3], r5_5=r5[5], r5_10=r5[10])
    if R is not None:
        out['raw'] = np.nanmean(R[m, t])
    if FE is not None:
        out['fe'] = np.nanmean(X[m, t] - FE[m])
    if XQ is not None:
        out['momq'] = np.nanmean(XQ[m, t])
    return out
