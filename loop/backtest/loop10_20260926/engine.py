# -*- coding: utf-8 -*-
"""loop10 엔진 (2026-09-26) — 7년 패널 numpy 그리드 버전.
확정방법 재현: eligible → mom20 → Rule H(1일>10% or 3일>20% 제외) → pool30 → (MOM 상위5 | LV σ20 하위5).
지표:
  A  = close(D) → close(D+1)            (현행 1차 지표)
  OO = open(D+1) → open(D+2)            (실집행: 아침 시가 매수·다음 아침 시가 교체, 겹침 없음)
  B  = open(D+1) → close(D+1)           (집행 구간)
  G  = close(D) → open(D+1)             (갭)
"""
import numpy as np, pandas as pd, os
from universe_filters import eligible

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = '069500'


def load(path=os.path.join(HERE, 'panel_ohlc_long.csv')):
    df = pd.read_csv(path, dtype={'code': str, 'date': str})
    names = df.groupby('code')['name'].last().to_dict()
    g = {}
    for f in ('open', 'high', 'low', 'close', 'volume'):
        g[f] = df.pivot(index='date', columns='code', values=f).sort_index()
    dates = list(g['close'].index)
    codes = list(g['close'].columns)
    P = {f: g[f].values.astype(float) for f in g}
    for f in ('open', 'high', 'low', 'close'):
        P[f][P[f] <= 0] = np.nan
    # 시가 결측/0 → 종가로 대체하지 않는다(OO 계산에서 제외)
    return P, dates, codes, names


class Engine:
    def __init__(self, P, dates, codes, names, mom=20):
        self.P, self.dates, self.codes, self.names = P, dates, codes, names
        C, O = P['close'], P['open']
        self.C, self.O = C, O
        T, N = C.shape
        self.T, self.N = T, N
        self.elig = np.array([eligible(names.get(c, '')) for c in codes])
        self.bi = codes.index(BENCH)
        # 종목별 일간 수익률(연속 가용일 기준 — 원 하네스와 동일하게 결측을 건너뛴 직전 가용값 대비)
        Cf = pd.DataFrame(C).ffill().values
        prev = np.vstack([np.full((1, N), np.nan), Cf[:-1]])
        R = (C / prev - 1) * 100
        R[np.isnan(C)] = np.nan
        self.R = R
        self.sig = {}
        # 전방 수익률 (행 i = 선정일 D)
        nxt = lambda X, k=1: np.vstack([X[k:], np.full((k, N), np.nan)])
        self.fA = (nxt(C) / C - 1) * 100
        self.fOO = (nxt(O, 2) / nxt(O, 1) - 1) * 100
        self.fB = (nxt(C) / nxt(O) - 1) * 100
        self.fG = (nxt(O) / C - 1) * 100
        self.fL1 = (nxt(C, 2) / nxt(C, 1) - 1) * 100   # 1일 지연 종가→종가 (종가 단일가 집행)
        st = np.abs(nxt(O) / C - 1) < 1e-9             # 익일 시가 == 전일 종가 (정적 시가 의심)
        self.fOOx = np.where(st, np.nan, self.fOO)
        # mom20 & Rule H
        def lag(X, k):
            return np.vstack([np.full((k, N), np.nan), X[:-k]])
        self.mom = (C / lag(C, mom) - 1) * 100
        r1 = (C / lag(C, 1) - 1) * 100
        r3 = (C / lag(C, 3) - 1) * 100
        hot = ((r1 > 10) & ~np.isnan(r1)) | ((r3 > 20) & ~np.isnan(r3))
        ok = self.elig[None, :] & ~np.isnan(self.mom) & ~hot
        self.ok = ok

    def vol(self, k=20, minp=None):
        key = ('vol', k)
        if key not in self.sig:
            self.sig[key] = pd.DataFrame(self.R).rolling(k, min_periods=minp or max(5, k // 3)).std().values
        return self.sig[key]

    def pool(self, i, n=30, score=None):
        """선정일 i 의 pool: ok 종목을 score(기본 mom20) 내림차순 상위 n (인덱스 배열)."""
        s = self.mom[i] if score is None else score[i]
        idx = np.where(self.ok[i] & ~np.isnan(s))[0]
        if len(idx) == 0:
            return idx
        o = idx[np.argsort(-s[idx], kind='stable')]
        return o[:n]

    def run(self, select, start=20, metrics=('A', 'OO', 'L1', 'OOx', 'B', 'G'), npick=5, require_full=True):
        """select(i, pool_idx) → 선택 인덱스 배열. 반환: DataFrame(date, A, OO, ... , bench_*)"""
        rows = []
        F = {'A': self.fA, 'OO': self.fOO, 'B': self.fB, 'G': self.fG, 'L1': self.fL1, 'OOx': self.fOOx}
        for i in range(start, self.T - 3):
            pl = self.pool(i)
            if len(pl) < npick:
                continue
            pk = select(i, pl)
            if pk is None or len(pk) == 0:
                continue
            a = self.fA[i, pk]
            if require_full and (np.isnan(a).any() or len(pk) < npick):
                continue
            row = {'i': i, 'date': self.dates[i]}
            for m in metrics:
                v = F[m][i, pk]
                row[m] = np.nanmean(v) if (~np.isnan(v)).any() else np.nan
                row['b' + m] = F[m][i, self.bi]
            rows.append(row)
        return pd.DataFrame(rows)

    # 기본 선택기
    def sel_mom(self, i, pl, n=5):
        return pl[:n]

    def sel_lv(self, i, pl, k=20, n=5, hi=False):
        v = self.vol(k)[i, pl]
        m = ~np.isnan(v)
        if m.sum() < n:
            return pl[:n]
        c, vv = pl[m], v[m]
        o = np.argsort(-vv if hi else vv, kind='stable')
        return c[o[:n]]


def prof(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    c = np.cumprod(1 + x / 100)
    pk = np.maximum.accumulate(c)
    yrs = len(x) / 252
    return dict(n=len(x), cum=(c[-1] - 1) * 100, cagr=(c[-1] ** (1 / yrs) - 1) * 100,
                mdd=((c / pk - 1).min()) * 100, sharpe=x.mean() / x.std(ddof=1) * 252 ** .5,
                mean=x.mean())


def fmt(p):
    return f"누적{p['cum']:+8.1f}% CAGR{p['cagr']:+6.1f}% MDD{p['mdd']:6.1f}% Sh{p['sharpe']:5.2f} 평균{p['mean']:+.4f}"


def tstat(d):
    d = np.asarray(d, float); d = d[~np.isnan(d)]
    return d.mean() / (d.std(ddof=1) / len(d) ** .5)


def r5(d):
    d = np.asarray(d, float); d = d[~np.isnan(d)]
    s = np.sort(d)[::-1]; n = len(d); tot = s.sum()
    out = {'mean': d.mean(), 'median': np.median(d)}
    for k in (1, 3, 5, 10):
        out[f'drop{k}'] = (tot - s[:k].sum()) / (n - k)
    lo, hi = np.quantile(d, [.02, .98])
    out['wins2'] = np.clip(d, lo, hi).mean()
    return out


def folds(d, K=3):
    d = np.asarray(d, float)
    n = len(d)
    return [np.nanmean(d[j * n // K:(j + 1) * n // K]) for j in range(K)]
