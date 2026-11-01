# -*- coding: utf-8 -*-
"""Rule VMX (r3_mom.md §2) — 신호·노출 계산.
슬리브: [6-3] mom150 상위5 (Rule H) 탈락청산, D 종가→D+1 종가.
σ̂_D = 슬리브 일수익(스케일 전) 최근 L 거래일 표본표준편차 (D 종가에 실현된 수익까지 = D 포함)
σ*_D = D 까지 σ̂ 의 확장창 중앙값, w_D = min(1, σ*/σ̂_D), K 거래일마다 갱신, |Δw|<0.10 이면 유지.
w_D 는 D 종가→D+1 종가 수익(행 i=D)에 곱한다. 나머지 현금(0).
"""
import sys
sys.path.insert(0, '/home/claude/w/test/common')
import numpy as np, pandas as pd
from dx import *  # noqa

SLEEVE_START = 250          # 슬리브 시작 선정일 index (mid.py START 와 동일 — HBG 표본과 공통)
WARM = 250                  # 슬리브 시작 후 250 거래일 평가 제외
EVAL0 = SLEEVE_START + WARM  # 평가 첫 선정일 index


def sleeve(frame='exit'):
    tg = targets(MOM[150], SLEEVE_START)
    df = run_exit(tg, SLEEVE_START) if frame == 'exit' else run_band(tg, SLEEVE_START)
    return df.set_index('i')


def sig_hat(r_by_i, L):
    """r_by_i: Series index=i(선정일), 값=i→i+1 수익. σ̂ at D=i uses rows i-L..i-1 (i 종가까지 실현)."""
    x = r_by_i.shift(1)  # 행 i 에 i-1→i 수익
    return x.rolling(L, min_periods=L).std(ddof=1)


def weights(sig, K=5, thr=0.10):
    s = sig.values
    med = pd.Series(s).expanding().median().values  # NaN 무시 확장 중앙값
    w = np.full(len(s), np.nan); cur = np.nan; k0 = None
    for j in range(len(s)):
        if not np.isfinite(s[j]):
            continue
        if k0 is None:
            k0 = j
        if (j - k0) % K == 0:
            cand = min(1.0, med[j] / s[j])
            if not np.isfinite(cur) or abs(cand - cur) >= thr:
                cur = cand
        w[j] = cur
    return pd.Series(w, index=sig.index)


def bench_by_i(idx):
    return pd.Series(FWD[np.asarray(idx), bi], index=idx)
