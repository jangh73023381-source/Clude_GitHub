# -*- coding: utf-8 -*-
"""Tester A 공용: loop10 엔진 로드 + 픽 생성 + 유동성 지표 (성과 계산 없음)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/w/loop/backtest/loop10_20260926')
from engine import *   # noqa
P, dates, codes, names = load('/home/claude/w/loop/backtest/panel_ohlc_long.csv')
E = Engine(P, dates, codes, names)
V = P['volume']; C = P['close']; O = P['open']
TV = pd.DataFrame(C * V).rolling(20, min_periods=20).mean().values   # 20일 평균 거래대금(원), D 포함
nxtO = np.vstack([O[1:], np.full((1, E.N), np.nan)])
STATIC = np.abs(nxtO / C - 1) < 1e-9          # D+1 시가 == D 종가 (engine fOOx 와 동일 정의)

def picks(sel, start=20, npick=5):
    """engine.run 과 동일한 표본 규칙(require_full: fA 결측 없는 5종)으로 픽만 반환 {i: idx array}."""
    out = {}
    for i in range(start, E.T - 3):
        pl = E.pool(i)
        if len(pl) < npick:
            continue
        pk = sel(i, pl)
        if pk is None or len(pk) < npick or np.isnan(E.fA[i, pk]).any():
            continue
        out[i] = np.asarray(pk)
    return out

def liq(pk):
    tv = np.concatenate([TV[i, p] for i, p in pk.items()])
    st = np.concatenate([STATIC[i, p] for i, p in pk.items()])
    ok = ~np.isnan(tv)
    return dict(slots=len(tv), lt1=(tv[ok] < 1e8).mean() * 100, lt5=(tv[ok] < 5e8).mean() * 100,
                med_tv=np.median(tv[ok]) / 1e8, static=st.mean() * 100)

def overlap(a, b):
    ks = sorted(set(a) & set(b))
    return np.mean([len(set(a[k]) & set(b[k])) for k in ks]), len(ks)

# ---------- 성과 계산 도구 (선행 점검 통과 후에만 사용) ----------
F = {'A': E.fA, 'OO': E.fOO, 'L1': E.fL1, 'OOx': E.fOOx}
def rets(pk, mets=('A', 'OO', 'L1', 'OOx')):
    ks = sorted(pk); rows = {'i': ks, 'date': [dates[k] for k in ks]}
    for m in mets:
        X = F[m]
        with np.errstate(all='ignore'):
            rows[m] = [np.nanmean(X[k, pk[k]]) if (~np.isnan(X[k, pk[k]])).any() else np.nan for k in ks]
    return pd.DataFrame(rows)

def sh(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return x.mean() / x.std(ddof=1) * 252 ** .5

def sbb_idx(n, B=2000, L=20, seed=20260929):
    """stationary block bootstrap 인덱스 (평균 블록 L)."""
    rng = np.random.default_rng(seed)
    p = 1.0 / L
    idx = np.empty((B, n), dtype=np.int64)
    st = rng.integers(0, n, size=(B, n)); nb = rng.random((B, n)) < p
    cur = st[:, 0].copy(); idx[:, 0] = cur
    for t in range(1, n):
        cur = np.where(nb[:, t], st[:, t], (cur + 1) % n); idx[:, t] = cur
    return idx

def boot_sh(x, idx):
    X = np.asarray(x, float)[idx]
    with np.errstate(all='ignore'):
        return np.nanmean(X, 1) / np.nanstd(X, 1, ddof=1) * 252 ** .5

def ci_shdiff(a, b, idx, q=(.05, .95)):
    d = boot_sh(a, idx) - boot_sh(b, idx)
    return sh(a) - sh(b), np.nanquantile(d, q[0]), np.nanquantile(d, q[1])

def deflated_sr(x, N):
    """Bailey & López de Prado DSR. 시행 간 SR 분산은 귀무(1/T) 가정."""
    from scipy.stats import norm, skew, kurtosis
    x = np.asarray(x, float); x = x[~np.isnan(x)]; T = len(x)
    sr = x.mean() / x.std(ddof=1); g = 0.5772156649
    v = 1.0 / T
    sr0 = np.sqrt(v) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * np.e)))
    g3 = skew(x); g4 = kurtosis(x, fisher=False)
    z = (sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
    return norm.cdf(z)
