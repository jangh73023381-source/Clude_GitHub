#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""박스권 경로 청산 — 원인 분리 대조군.

문제: 경로 청산(상단 목표·하단 손절)이 시간 청산보다 -3%p 이상 나빴다. 그런데 이것이
      ① '지지선(박스 하단) 매수'가 나쁜 탓인지, ② 청산 구조(타이트한 손절) 자체가
      누구에게나 나쁜 탓인지 구분되지 않는다. 구분하지 못하면 잘못된 결론을 낸다.

설계: 같은 종목·같은 청산 규칙을 **무작위 진입일**에 적용해 대조한다.
      같은 종목 풀에서 이벤트 수만큼 진입일을 무작위 추출(시드 고정) × 20회 반복.
      대조군도 똑같이 그날의 lo60/hi60을 박스로 삼는다 — 진입 조건만 다르다.

  대조군도 비슷하게 나쁘다  → 원인은 청산 구조. '박스 하단 매수'는 무죄(별개 검정 필요).
  대조군이 훨씬 낫다        → 원인은 지지선 매수. 기존 기각 결론이 경로 청산에서도 재확인.

조회 전용.
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
BOX, LOOKBACK, CAP, COST = 60, 250, 20, 0.10
NREP = 20
EXITS = [('base', None, None), ('top_s2', 1.00, 0.02), ('mid_s2', 0.50, 0.02)]


def simulate(o, h, lo, c, lo60, hi60, i, bench_map, d):
    """진입 i에서 청산 규칙별 (초과수익, 보유일) 반환."""
    width = hi60[i] - lo60[i]
    if not np.isfinite(width) or width <= 0:
        return None
    res = {}
    for tag, tgt_f, stop_f in EXITS:
        if tgt_f is None:
            j = i + 5
            ret, days = (c[j] / c[i] - 1) * 100, 5
        else:
            target, stop = lo60[i] + width * tgt_f, lo60[i] * (1 - stop_f)
            px, days = None, CAP
            for k in range(1, CAP + 1):
                j = i + k
                if lo[j] <= stop:
                    px, days = min(o[j], stop), k
                    break
                if h[j] >= target:
                    px, days = max(o[j], target), k
                    break
            if px is None:
                px = c[i + CAP]
            ret = (px / c[i] - 1) * 100
        b = bench_map.get((d[i], d[i + days]), np.nan)
        res[tag] = (ret - b - COST, days)
    return res


def main():
    df = pd.read_csv(PANEL, dtype={'code': str})
    df['code'] = df['code'].str.zfill(6)
    bser = df[df['code'] == BENCH].set_index('date')['close'].astype(float)
    df = df[df['name'].map(eligible) | (df['code'] == BENCH)]

    ev = pd.read_csv(os.path.join(HERE, 'box_exit_events.csv'), dtype={'code': str})
    n_by_code = ev.groupby('code').size().to_dict()

    bench_map = {}
    treat = {t: [] for t, _, _ in EXITS}
    ctrl = {t: [[] for _ in range(NREP)] for t, _, _ in EXITS}

    for code, g in df.groupby('code', sort=False):
        if code not in n_by_code:
            continue
        g = g.sort_values('date')
        d = g['date'].to_numpy()
        o, h = g['open'].to_numpy(float), g['high'].to_numpy(float)
        lo, c = g['low'].to_numpy(float), g['close'].to_numpy(float)
        n = len(c)
        lo60 = pd.Series(lo).shift(1).rolling(BOX, min_periods=BOX).min().to_numpy()
        hi60 = pd.Series(h).shift(1).rolling(BOX, min_periods=BOX).max().to_numpy()

        valid = np.arange(LOOKBACK, n - CAP)
        if len(valid) == 0:
            continue
        for i in valid:
            for k in (5, CAP):
                bench_map.setdefault((d[i], d[i + k]), np.nan)
        for k in range(1, CAP + 1):
            for i in valid:
                key = (d[i], d[i + k])
                if key not in bench_map or not np.isfinite(bench_map.get(key, np.nan)):
                    try:
                        bench_map[key] = (bser.loc[d[i + k]] / bser.loc[d[i]] - 1) * 100
                    except KeyError:
                        bench_map[key] = np.nan

        # 처치군: 실제 이벤트일
        ev_i = ev[ev['code'] == code]['date'].tolist()
        pos = {int(x): k for k, x in enumerate(d)}
        for dt in ev_i:
            i = pos.get(int(dt))
            if i is None or i < LOOKBACK or i + CAP >= n:
                continue
            r = simulate(o, h, lo, c, lo60, hi60, i, bench_map, d)
            if r:
                for t in treat:
                    treat[t].append(r[t][0])
        # 대조군: 같은 개수만큼 무작위 진입
        m = n_by_code[code]
        for rep in range(NREP):
            rng = np.random.default_rng(1000 * rep + int(code[-4:], 36) % 997)
            pick = rng.choice(valid, size=min(m, len(valid)), replace=False)
            for i in pick:
                r = simulate(o, h, lo, c, lo60, hi60, i, bench_map, d)
                if r:
                    for t in ctrl:
                        ctrl[t][rep].append(r[t][0])

    print('원인 분리 — 지지선 진입(처치군) vs 무작위 진입(대조군), 청산 규칙 동일')
    print(f'대조군 {NREP}회 반복 · 초과수익 %p (KODEX200 대비, 왕복 10bp 차감)\n')
    rows = []
    for t, _, _ in EXITS:
        a = np.array(treat[t], float)
        a = a[np.isfinite(a)]
        cm = [np.nanmean(x) for x in ctrl[t] if len(x)]
        rows.append(dict(청산=t, 처치군=round(a.mean(), 3), 처치n=len(a),
                         대조군평균=round(float(np.mean(cm)), 3),
                         대조군최소=round(float(np.min(cm)), 3),
                         대조군최대=round(float(np.max(cm)), 3),
                         차이=round(a.mean() - float(np.mean(cm)), 3)))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    main()
