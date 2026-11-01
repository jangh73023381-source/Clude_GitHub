# -*- coding: utf-8 -*-
"""공유 탈락청산 엔진 (Tester B, 2026-09-29) — VMX·HBG 공용.

데이터·유니버스·Rule H 는 loop10 mid.py 와 동일(eligible, okH).
틀
  run_exit(targets)            : 탈락청산(Rule CB 청산축), 보유집합 = 그날의 목표5, D 종가 → D+1 종가, 동일가중.
                                 (reset.py ① 과 같은 수익 정의: 두 종가가 모두 있는 보유 종목의 단순평균, 없으면 0)
  run_band(targets)            : 탈락청산 + Rule CB 진입 밴드(-0.5% <= r_D < +1.5%, 0종 통과 시 -1.0% 로 1회 확장),
                                 슬롯당 자본 20%, 못 산 슬롯은 현금(0), 다음 날 재판정.
선정은 D 종가까지의 정보만 사용. 비용 0.
"""
import os, sys
import numpy as np, pandas as pd

LOOP = '/home/claude/w/loop/backtest/loop10_20260926'
sys.path.insert(0, LOOP)
_cwd = os.getcwd(); os.chdir(LOOP)
import mid  # noqa: E402  (engine.load → 같은 패널)
os.chdir(_cwd)
from engine import prof, tstat, r5, folds  # noqa: E402,F401

E = mid.E
C = mid.C; T, N = C.shape
dates = mid.dates; codes = mid.codes; names = mid.names
bi = E.bi
MOM = mid.MOM            # {k: %}
okH = mid.okH            # eligible ∩ ~RuleH
elig = E.elig
Rd = E.R / 100.0         # 당일 등락률(직전 가용 종가 대비) — 밴드 판정용

nxt = np.vstack([C[1:], np.full((1, N), np.nan)])
FWD = nxt / C - 1        # 행 i: D=i 종가 → D+1 종가 (reset.py 와 동일 정의)


def lag(X, k):
    return np.vstack([np.full((k, X.shape[1]), np.nan), X[:-k]])


def top_k(score, i, n=5, mask=okH, tie=None, min_univ=5):
    s = score[i]
    m = mask[i] & ~np.isnan(s) & ~np.isnan(C[i])
    idx = np.where(m)[0]
    if len(idx) < max(n, min_univ):
        return np.array([], int)
    if tie is None:
        o = np.argsort(-s[idx], kind='stable')
    else:
        t = tie[i, idx]
        o = np.lexsort((-np.nan_to_num(t, nan=-1e18), -s[idx]))
    return idx[o[:n]]


def targets(score, start, mask=okH, tie=None, min_univ=5):
    return {i: top_k(score, i, mask=mask, tie=tie, min_univ=min_univ) for i in range(start, T - 1)}


def run_exit(tg, start):
    """탈락청산 틀. 반환 DataFrame(i=선정일, date=실현일 D+1, r=일수익, n=보유수)."""
    out = []
    for i in range(start, T - 1):
        t = tg.get(i, np.array([], int))
        v = FWD[i, t] if len(t) else np.array([])
        v = v[np.isfinite(v)]
        out.append((i, dates[i + 1], float(v.mean()) if len(v) else 0.0, len(t)))
    return pd.DataFrame(out, columns=['i', 'date', 'r', 'n'])


def run_band(tg, start, lo=-0.005, hi=0.015, lo2=-0.010, slot=0.2):
    """탈락청산 + Rule CB 진입 밴드. 보유 중인 목표 종목은 밴드와 무관하게 유지."""
    hold = set(); out = []; buys = 0; widened = 0; cand_days = 0
    for i in range(start, T - 1):
        t = set(tg.get(i, np.array([], int)).tolist())
        hold &= t                                   # 1. 탈락 종목 D 종가 매도
        cand = [c for c in t if c not in hold]      # 2. 미보유 목표
        if cand:
            cand_days += 1
            rr = {c: Rd[i, c] for c in cand}
            ok = [c for c in cand if np.isfinite(rr[c]) and lo <= rr[c] < hi]
            if not ok:                               # 3. 0종 통과 → 1회 확장
                ok = [c for c in cand if np.isfinite(rr[c]) and lo2 <= rr[c] < hi]
                if ok:
                    widened += 1
            hold |= set(ok); buys += len(ok)
        h = np.array(sorted(hold), int)
        v = FWD[i, h] if len(h) else np.array([])
        v = np.where(np.isfinite(v), v, 0.0)
        out.append((i, dates[i + 1], float(slot * v.sum()), len(h)))
    df = pd.DataFrame(out, columns=['i', 'date', 'r', 'n'])
    df.attrs.update(buys=buys, widened=widened, cand_days=cand_days)
    return df


# ---------------- 통계 ----------------
def sharpe(x):
    x = np.asarray(x, float)
    s = x.std(ddof=1)
    return x.mean() / s * np.sqrt(252) if s > 0 else np.nan


def stats(x):
    x = np.asarray(x, float)
    eq = np.cumprod(1 + x)
    yrs = len(x) / 252
    return dict(cum=(eq[-1] - 1) * 100, cagr=(eq[-1] ** (1 / yrs) - 1) * 100,
                mdd=(eq / np.maximum.accumulate(eq) - 1).min() * 100, sh=sharpe(x), n=len(x))


def sb_indices(n, B=2000, mean_block=20, seed=20260929):
    """stationary block bootstrap 인덱스 (Politis–Romano, 원형), shape (B, n)."""
    rng = np.random.default_rng(seed)
    p = 1.0 / mean_block
    idx = np.empty((B, n), np.int64)
    idx[:, 0] = rng.integers(0, n, B)
    newb = rng.random((B, n)) < p
    rs = rng.integers(0, n, (B, n))
    for t in range(1, n):
        idx[:, t] = np.where(newb[:, t], rs[:, t], (idx[:, t - 1] + 1) % n)
    return idx


_IDX = {}


def boot_diff(a, b, fn='sharpe', B=2000, seed=20260929, alpha=0.10):
    """쌍(a,b) 같은 인덱스로 재표집한 통계 차(a-b)의 90% CI."""
    a = np.asarray(a, float); b = np.asarray(b, float); n = len(a)
    key = (n, B, seed)
    if key not in _IDX:
        _IDX[key] = sb_indices(n, B, 20, seed)
    I = _IDX[key]
    A = a[I]; Bm = b[I]
    if fn == 'sharpe':
        f = lambda X: X.mean(1) / X.std(1, ddof=1) * np.sqrt(252)
    elif fn == 'cagr':
        f = lambda X: (np.exp(np.log1p(X).sum(1) / (n / 252)) - 1) * 100
    elif fn == 'mean':
        f = lambda X: X.mean(1)
    d = f(A) - f(Bm)
    return np.quantile(d, alpha / 2), np.quantile(d, 1 - alpha / 2), d


def dsr(x, n_trials, sr_var_ann=None):
    """Deflated Sharpe (Bailey–López de Prado). 일간 SR 기준. 시행 간 SR 분산은 연 0.5² 가정(보고용)."""
    from math import sqrt, e
    from scipy.stats import norm, skew, kurtosis
    x = np.asarray(x, float); T_ = len(x)
    sr = x.mean() / x.std(ddof=1)
    v = (0.5 ** 2 / 252) if sr_var_ann is None else sr_var_ann / 252
    g = 0.5772156649
    sr0 = sqrt(v) * ((1 - g) * norm.ppf(1 - 1 / n_trials) + g * norm.ppf(1 - 1 / (n_trials * e)))
    sk = skew(x); ku = kurtosis(x, fisher=False)
    z = (sr - sr0) * sqrt(T_ - 1) / sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2)
    return float(norm.cdf(z)), float(sr0 * np.sqrt(252))
