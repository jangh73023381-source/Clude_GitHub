# -*- coding: utf-8 -*-
"""Rule HBG (r3_ens.md) — 점수·목표집합.
유니버스: okH(eligible ∩ Rule H) ∩ mom150 산출 가능 ∩ 종가 존재.
S_i = mean_{k∈A_i} pct_k(mom_k,i), pct_k = 선정일 D 에 mom_k 산출 가능한 okH 종목들 안의 횡단면 백분위(평균 순위, 0~1).
상위5, 동점 mom150 내림차순. 선정일 index ≥ 250.
"""
import sys
sys.path.insert(0, '/home/claude/w/test/common')
import numpy as np, pandas as pd
from scipy.stats import rankdata
from dx import *  # noqa

START = 250


def pct_matrix(X, base_mask):
    P = np.full(X.shape, np.nan)
    for i in range(START, T):
        m = base_mask[i] & ~np.isnan(X[i])
        idx = np.where(m)[0]
        if len(idx) == 0:
            continue
        if len(idx) == 1:
            P[i, idx] = 0.5; continue
        rk = rankdata(X[i, idx], method='average')
        P[i, idx] = (rk - 1) / (len(idx) - 1)
    return P


_PC = {}


def pct(k):
    if k not in _PC:
        _PC[k] = pct_matrix(MOM[k], okH & ~np.isnan(C))
    return _PC[k]


def hbg_score(K=(120, 150, 200, 250), extra=None):
    """extra: 추가 백분위 행렬 목록(지속형 무작위·무관 신호 대조용)."""
    elig150 = okH & ~np.isnan(MOM[150]) & ~np.isnan(C)
    mats = [pct(k) for k in K] + (extra or [])
    st = np.stack(mats)
    S = np.nanmean(np.where(np.isnan(st), np.nan, st), axis=0) if len(mats) > 1 else st[0]
    S = np.where(elig150, S, np.nan)
    return S


def tg_of(S):
    return targets(S, START, tie=MOM[150])
