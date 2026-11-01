# -*- coding: utf-8 -*-
"""공통: 엔진 로드 + stationary block bootstrap (TEST_RULES: 블록 20, 2000회, seed 20260929)."""
import sys, numpy as np
sys.path.insert(0, '/home/claude/w/loop/backtest/loop10_20260926')
from engine import load, Engine, prof, folds, r5, tstat  # noqa

SEED = 20260929


def sbb_idx(n, B=2000, L=20, seed=SEED):
    """stationary block bootstrap 인덱스 (B x n). 기하분포 블록 길이 평균 L, 원형 연결."""
    rng = np.random.default_rng(seed)
    p = 1.0 / L
    idx = np.empty((B, n), dtype=np.int64)
    for b in range(B):
        start = rng.integers(0, n, size=n)
        newblk = rng.random(n) < p
        newblk[0] = True
        out = np.empty(n, dtype=np.int64)
        cur = 0
        for t in range(n):
            cur = start[t] if newblk[t] else (cur + 1) % n
            out[t] = cur
        idx[b] = out
    return idx


def sharpe(x, axis=-1):
    return x.mean(axis=axis) / x.std(axis=axis, ddof=1) * np.sqrt(252)


def mdd(x):
    c = np.cumprod(1 + np.asarray(x) / 100)
    return ((c / np.maximum.accumulate(c)) - 1).min() * 100
