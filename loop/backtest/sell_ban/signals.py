#!/usr/bin/env python3
"""매도 신호 후보 — 사전 등록 목록(2026-09-11, 결과를 보기 전에 확정). 전부 신호일 D 종가까지의 정보만 쓴다."""
import numpy as np
from engine import sh, rmin, rmax, xrank


def prev(b):
    p = np.zeros_like(b); p[:, 1:] = b[:, :-1]; return p


def cross(b):
    return b & ~prev(b)


def build(I):
    O, H, L, C, V = I['O'], I['H'], I['L'], I['C'], I['V']
    MA5, MA10, MA20, MA60, VA = I['MA5'], I['MA10'], I['MA20'], I['MA60'], I['VA']
    C1, O1, M20_1, M60_1 = sh(C, 1), sh(O, 1), sh(MA20, 1), sh(MA60, 1)
    R1 = I['RET1']
    with np.errstate(invalid='ignore'):
        S = {}
        base_eng = (C1 >= M20_1) & (C1 > O1) & (C < O) & (C <= O1) & (C <= L + (H - L) * 0.4)
        S['F1a 역장악형+거래량(EG 대칭)'] = base_eng & (V >= VA * 1.3)
        S['F1b 역장악형'] = base_eng
        brk20 = (C < MA20) & (C1 >= M20_1)
        S['F2a MA20 하향이탈'] = brk20
        S['F2b MA20 이탈+거래량1.3배'] = brk20 & (V >= VA * 1.3)
        S['F2c MA20 이탈+MA20 하락'] = brk20 & (MA20 < M20_1)
        S['F3a 데드크로스 5/20'] = cross(MA5 < MA20)
        S['F3b 데드크로스 10/20'] = cross(MA10 < MA20)
        S['F3c 데드크로스 20/60'] = cross(MA20 < MA60)
        brk60 = (C < MA60) & (C1 >= M60_1)
        S['F4a MA60 하향이탈'] = brk60
        S['F4b MA60 이탈+MA60 하락'] = brk60 & (MA60 < sh(MA60, 5))
        for n in (20, 60, 120):
            lo = sh(rmin(L, n), 1)
            S[f'F5 {n}일 저점 이탈'] = cross(C < lo)
        dd = C / rmax(H, 60) - 1
        for x in (8, 12, 16, 20):
            S[f'F6 60일고점 대비 -{x}%'] = cross(dd <= -x / 100)
        for x in (3, 4, 5, 7):
            S[f'F7 급락일 -{x}%'] = R1 <= -x / 100
        gap = C / MA20 - 1
        for x in (8, 12, 16, 20):
            S[f'F8 MA20 이격 +{x}%'] = cross(gap >= x / 100)
        c3 = C / sh(C, 3) - 1
        for x in (10, 15, 20):
            S[f'F9 3일 누적 +{x}%'] = cross(c3 >= x / 100)
        for x in (7, 10):
            S[f'F9 1일 급등 +{x}%'] = R1 >= x / 100
        for x in (75, 80, 85):
            S[f'F10 RSI14 {x} 돌파'] = cross(I['RSI'] >= x)
        body = np.abs(C - O); upper = H - np.maximum(O, C)
        S['F11 고점 윗꼬리+거래량'] = (upper >= 2 * body) & (H >= rmax(H, 20)) & (V >= VA * 1.5) & (H > L)
        pr = xrank(I['MOM20'])
        for q in (10, 20):
            S[f'F12 mom20 하위 {q}% 진입'] = cross(pr <= q / 100)
        S['F13 MA20 하락전환+종가<MA20'] = (MA20 < M20_1) & (M20_1 >= sh(MA20, 2)) & (C < MA20)
        S['F14 역배열 진입'] = cross((MA5 < MA20) & (MA20 < MA60))
        S['F15 -2%·거래량2배'] = (R1 <= -0.02) & (V >= VA * 2)
        S['F15 -3%·거래량2배'] = (R1 <= -0.03) & (V >= VA * 2)
    return {k: np.nan_to_num(v, nan=0).astype(bool) for k, v in S.items()}
