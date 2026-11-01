#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""박스권 하단매수 — 경로 기반 청산 검정 (최소 설계).

질문: "박스 하단에서 사서 박스 상단에서 판다"가 기존 기각(2026-08-04 지지선 매수)을
      뒤집는가? 기존 검정은 청산이 전부 시간 기반(H=1·3·5·10·20)이라 경로 기반
      청산(목표 도달 / 손절 이탈)을 원리적으로 볼 수 없었다.

설계 (시행 5조합 — 다중검정 최소화)
  이벤트  : lo60 수성(hold) · 준수 5회 이상  ← 2026-08-04 검정의 유일한 생존 후보
  박스     : 하단 = lo60(직전 60일 최저가, 당일 제외) · 상단 = hi60(직전 60일 최고가)
  진입     : D 종가
  청산 5종 :
      base   시간 기반 H=5 종가 청산                     (기존 baseline 재현)
      top_s2 목표 = 상단        · 손절 = 하단 -2% · 캡 20일
      top_s4 목표 = 상단        · 손절 = 하단 -4% · 캡 20일
      mid_s2 목표 = 하단+폭50%  · 손절 = 하단 -2% · 캡 20일
      mid_s4 목표 = 하단+폭50%  · 손절 = 하단 -4% · 캡 20일
  체결     : D+1부터 일별 판정. 같은 날 손절·목표 동시 충족이면 손절 우선(보수적).
             갭 통과 시 시가 체결(손절 min(open,stop) · 목표 max(open,target)).
  지표     : excess = 보유기간 수익률 - KODEX200 동기간 수익률, 왕복 10bp 차감
             alpha  = excess - 그 종목의 무조건 평균 excess(동일 보유일수 매칭)

박스 유형(우상향/횡보/우하향)은 이번 시행에서 조건으로 걸지 않고 사후 분해로만 기록한다
(조건으로 걸면 시행 횟수가 3배가 되어 과최적화 가드가 무의미해진다).

조회 전용 — 주문·매매 기능 없음.
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'references', 'scripts'))
from universe_filters import eligible  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel_ohlc_2y.csv')
BENCH = '069500'

TOL = 0.010        # 터치 허용오차
BREAK = 0.010      # 이탈 판정
BOX = 60           # 박스 룩백
LOOKBACK = 250     # 준수 이력 룩백
KCUT = 5           # 준수 횟수 컷
CAP = 20           # 최대 보유일
COST = 0.10        # 왕복 비용 %

EXITS = [
    ('base',   None,  None),
    ('top_s2', 1.00, 0.02),
    ('top_s4', 1.00, 0.04),
    ('mid_s2', 0.50, 0.02),
    ('mid_s4', 0.50, 0.04),
]


def rolling_prev(a, w, fn):
    """당일 제외 직전 w일 롤링 (shift(1) 적용)."""
    s = pd.Series(a)
    return s.shift(1).rolling(w, min_periods=w).agg(fn).to_numpy()


def slope_pct(c, w=BOX):
    """직전 w일 종가 회귀 기울기 (일평균 %, 당일 제외) — 박스 유형 분류용."""
    s = pd.Series(c).shift(1)
    x = np.arange(w)
    xm = x.mean()
    denom = ((x - xm) ** 2).sum()

    def f(y):
        ym = y.mean()
        if ym <= 0:
            return np.nan
        return (((x - xm) * (y - ym)).sum() / denom) / ym * 100.0

    return s.rolling(w, min_periods=w).apply(f, raw=True).to_numpy()


def build_events(df, bench):
    out = []
    for code, g in df.groupby('code', sort=False):
        g = g.sort_values('date')
        if len(g) < LOOKBACK + CAP + 5:
            continue
        d = g['date'].to_numpy()
        o = g['open'].to_numpy(float)
        h = g['high'].to_numpy(float)
        lo = g['low'].to_numpy(float)
        c = g['close'].to_numpy(float)
        n = len(c)

        lo60 = rolling_prev(lo, BOX, 'min')
        hi60 = rolling_prev(h, BOX, 'max')
        slp = slope_pct(c)

        touch = np.isfinite(lo60) & (lo <= lo60 * (1 + TOL))
        hold = touch & (c >= lo60) & (lo >= lo60 * (1 - BREAK))
        brk = touch & ~hold

        ph = pd.Series(hold.astype(float)).shift(1).rolling(LOOKBACK, min_periods=1).sum().to_numpy()
        pb = pd.Series(brk.astype(float)).shift(1).rolling(LOOKBACK, min_periods=1).sum().to_numpy()

        idx = np.where(hold & (ph >= KCUT))[0]
        idx = idx[(idx >= LOOKBACK) & (idx + CAP < n)]
        for i in idx:
            width = hi60[i] - lo60[i]
            if not np.isfinite(width) or width <= 0:
                continue
            rec = dict(code=code, date=int(d[i]), entry=c[i],
                       low=lo60[i], high=hi60[i], width_pct=width / c[i] * 100.0,
                       slope=slp[i], prior_hold=ph[i], prior_break=pb[i])
            for tag, tgt_f, stop_f in EXITS:
                if tgt_f is None:
                    j = i + 5
                    rec[f'{tag}_ret'] = (c[j] / c[i] - 1) * 100
                    rec[f'{tag}_days'] = 5
                    rec[f'{tag}_why'] = 'time'
                    rec[f'{tag}_bench'] = bench_ret(bench, d[i], d[j])
                    continue
                target = lo60[i] + width * tgt_f
                stop = lo60[i] * (1 - stop_f)
                px, days, why = None, CAP, 'cap'
                for k in range(1, CAP + 1):
                    j = i + k
                    if lo[j] <= stop:
                        px, days, why = min(o[j], stop), k, 'stop'
                        break
                    if h[j] >= target:
                        px, days, why = max(o[j], target), k, 'target'
                        break
                if px is None:
                    px = c[i + CAP]
                rec[f'{tag}_ret'] = (px / c[i] - 1) * 100
                rec[f'{tag}_days'] = days
                rec[f'{tag}_why'] = why
                rec[f'{tag}_bench'] = bench_ret(bench, d[i], d[i + days])
            out.append(rec)
    return pd.DataFrame(out)


_BC = {}


def bench_ret(bench, d0, d1):
    key = (d0, d1)
    if key in _BC:
        return _BC[key]
    try:
        a = bench.loc[d0]
        b = bench.loc[d1]
        v = (b / a - 1) * 100
    except KeyError:
        v = np.nan
    _BC[key] = v
    return v


def main():
    df = pd.read_csv(PANEL, dtype={'code': str})
    df['code'] = df['code'].str.zfill(6)
    bench = df[df['code'] == BENCH].set_index('date')['close'].astype(float)
    keep = df['name'].map(eligible) | (df['code'] == BENCH)
    df = df[keep]
    ev = build_events(df, bench)
    ev.to_csv(os.path.join(HERE, 'box_exit_events.csv'), index=False)
    print(f'events={len(ev)} codes={ev["code"].nunique()} '
          f'dates={ev["date"].min()}~{ev["date"].max()}')


if __name__ == '__main__':
    main()
