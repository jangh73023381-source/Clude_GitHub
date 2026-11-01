#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETF 지지선 준수(respect) 백테스트 — 엔진.

질문: "지지선을 몇 번 지켜주는 ETF가 있고, 그 지지선에 왔을 때 사면 좋은가?"

설계
  · 지지선 후보 8종 (전부 D-1까지의 정보만 사용 — 룩어헤드 없음)
      ma20 / ma60 / ma120   : 이동평균
      lo20 / lo60 / lo120   : 직전 N일 최저가 (당일 제외)
      poc120 / poc250       : 매물대 — 최근 N일 거래량을 각 일의 저가~고가에 균등 배분해
                              가격구간별로 집계한 뒤, 현재가 아래에서 가장 두꺼운 구간
  · 터치(touch) : low_D <= level*(1+TOL)
  · 수성(hold)  : 터치이면서 close_D >= level 이고 low_D >= level*(1-BREAK)  → "지켜줬다"
  · 이탈(break) : 터치했으나 위 조건 미충족
  · 준수이력    : 과거 LOOKBACK일 안의 hold/break 횟수 (당일 제외 — shift(1))
  · 이벤트      : hold 발생일 D 종가 매수 → H일 뒤 종가 매도
  · 지표        : excess = 수익률 - KODEX200 동기간, alpha = excess - 그 종목 무조건 평균 excess

조회 전용 — 주문·매매 기능 없음.
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'references', 'scripts'))
from universe_filters import eligible  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel_ohlc_2y.csv')
BENCH_CODE = '069500'

TOL = 0.010
BREAK = 0.010
LOOKBACK = 250
NBIN = 120
HORIZONS = [1, 3, 5, 10, 20]
LEVELS = ['ma20', 'ma60', 'ma120', 'lo20', 'lo60', 'lo120', 'poc120', 'poc250']


def poc_matrix(high, low, close, vol, wins):
    """매물대 POC를 전 구간 벡터화 계산.

    가격 그리드를 종목 전체 구간에 대해 한 번 고정하고, 각 일의 거래량을 저가~고가에
    비례 배분한 (n, NBIN) 가중치 행렬을 만든 뒤 누적합으로 롤링 윈도 집계를 얻는다.
    """
    n = len(close)
    lo, hi = np.nanmin(low), np.nanmax(high)
    out = {f'poc{w}': np.full(n, np.nan) for w in wins}
    if not np.isfinite(lo) or hi <= lo:
        return out
    edges = np.linspace(lo, hi, NBIN + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    a = np.where(np.isfinite(low), low, 0.0)[:, None]
    b = np.where(np.isfinite(high), high, 0.0)[:, None]
    b = np.maximum(b, a * 1.0001)
    ov = np.clip(np.minimum(edges[None, 1:], b) - np.maximum(edges[None, :-1], a), 0, None)
    s = ov.sum(axis=1, keepdims=True)
    s[s == 0] = 1.0
    v = np.nan_to_num(vol)[:, None]
    W = v * ov / s                      # (n, NBIN) 일별 거래량 배분
    C = np.vstack([np.zeros(NBIN), np.cumsum(W, axis=0)])
    for w in wins:
        if n <= w:
            continue
        idx = np.arange(w, n)
        acc = C[idx] - C[idx - w]       # 직전 w일 누적 (당일 제외)
        px = close[idx - 1][:, None]
        masked = np.where(centers[None, :] < px * 0.999, acc, -1.0)
        best = masked.argmax(axis=1)
        val = np.where(masked.max(axis=1) > 0, centers[best], np.nan)
        out[f'poc{w}'][idx] = val
    return out


def build_levels(g):
    c = g['close'].to_numpy(float)
    h = g['high'].to_numpy(float)
    l = g['low'].to_numpy(float)
    v = g['volume'].to_numpy(float)
    s = pd.Series(c)
    out = {}
    for w in (20, 60, 120):
        out[f'ma{w}'] = s.rolling(w).mean().shift(1).to_numpy()
        out[f'lo{w}'] = pd.Series(l).rolling(w).min().shift(1).to_numpy()
    out.update(poc_matrix(h, l, c, v, (120, 250)))
    return out


def main():
    d = pd.read_csv(PANEL, dtype={'code': str})
    d['code'] = d['code'].str.zfill(6)
    d = d.sort_values(['code', 'date']).reset_index(drop=True)
    names = d.groupby('code')['name'].last()
    bench = d[d.code == BENCH_CODE].drop_duplicates('date').set_index('date')['close']

    keep = {c for c in names.index if eligible(names[c])}
    print(f'유니버스 {len(names)}종 → 필터 후 {len(keep)}종', file=sys.stderr)

    rows, base_rows = [], []
    maxH = max(HORIZONS)
    for code, g in d.groupby('code', sort=False):
        if code not in keep or len(g) < 300:
            continue
        g = g.reset_index(drop=True)
        dates = g['date'].to_numpy()
        c = g['close'].to_numpy(float)
        l = g['low'].to_numpy(float)
        n = len(g)
        bpx = bench.reindex(dates).to_numpy(float)

        rec = {'code': code}
        for H in HORIZONS:
            r = c[H:] / c[:-H] - 1
            bb = bpx[H:] / bpx[:-H] - 1
            rec[f'base{H}'] = np.nanmean((r - bb) * 100)
        base_rows.append(rec)

        lv = build_levels(g)
        for lname in LEVELS:
            level = lv[lname]
            valid = np.isfinite(level)
            touch = valid & (l <= level * (1 + TOL))
            held = touch & (c >= level) & (l >= level * (1 - BREAK))
            brk = touch & ~held
            hs = pd.Series(held.astype(float)).rolling(LOOKBACK, min_periods=1).sum().shift(1).to_numpy()
            bs = pd.Series(brk.astype(float)).rolling(LOOKBACK, min_periods=1).sum().shift(1).to_numpy()
            for i in np.flatnonzero(held):
                if i < 130 or i >= n - maxH:
                    continue
                r = {'code': code, 'name': names[code], 'level': lname,
                     'date': int(dates[i]),
                     'prior_hold': 0.0 if not np.isfinite(hs[i]) else hs[i],
                     'prior_break': 0.0 if not np.isfinite(bs[i]) else bs[i],
                     'dist': (c[i] / level[i] - 1) * 100}
                for H in HORIZONS:
                    j = i + H
                    r[f'ret{H}'] = (c[j] / c[i] - 1) * 100
                    r[f'bench{H}'] = (bpx[j] / bpx[i] - 1) * 100
                rows.append(r)

    pd.DataFrame(rows).to_csv(os.path.join(HERE, 'support_events.csv'), index=False)
    pd.DataFrame(base_rows).to_csv(os.path.join(HERE, 'support_baseline.csv'), index=False)
    print(f'이벤트 {len(rows)}건 저장', file=sys.stderr)


if __name__ == '__main__':
    main()
