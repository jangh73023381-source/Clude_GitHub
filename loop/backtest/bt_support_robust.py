#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""지지선 이벤트 강건성 검정.

전체 스윕에서 살아남은 후보(lo60 계열)를 대상으로
  R1. 수성(hold) vs 이탈(break) 대조 — "지켜줬다"는 사실 자체에 정보가 있는가
  R2. 종목 잭나이프
  R3. 분기별 안정성
  R4. 왕복비용 10bp 차감 후 실집행 성과 (KODEX200 대비)
  R5. 다중검정 보정 (Bonferroni / Deflated t)
를 수행한다.
"""
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'references', 'scripts'))
from universe_filters import eligible  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TOL, BREAK, LOOKBACK = 0.010, 0.010, 250
HORIZONS = [1, 3, 5, 10, 20]
COST = 0.10  # 왕복 10bp (%)


def tstat(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    return np.nan if len(x) < 3 else x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))


def build_break_events(win=60):
    """lo{win} 터치 중 '이탈'한 날의 사후 수익률 — 수성 이벤트와 대조하기 위함."""
    d = pd.read_csv(os.path.join(HERE, 'panel_ohlc_2y.csv'), dtype={'code': str})
    d['code'] = d['code'].str.zfill(6)
    d = d.sort_values(['code', 'date']).reset_index(drop=True)
    names = d.groupby('code')['name'].last()
    bench = d[d.code == '069500'].drop_duplicates('date').set_index('date')['close']
    keep = {c for c in names.index if eligible(names[c])}
    rows = []
    for code, g in d.groupby('code', sort=False):
        if code not in keep or len(g) < 300:
            continue
        g = g.reset_index(drop=True)
        dates = g['date'].to_numpy(); c = g['close'].to_numpy(float); l = g['low'].to_numpy(float)
        bpx = bench.reindex(dates).to_numpy(float); n = len(g)
        level = pd.Series(l).rolling(win).min().shift(1).to_numpy()
        valid = np.isfinite(level)
        touch = valid & (l <= level * (1 + TOL))
        held = touch & (c >= level) & (l >= level * (1 - BREAK))
        brk = touch & ~held
        hs = pd.Series(held.astype(float)).rolling(LOOKBACK, min_periods=1).sum().shift(1).to_numpy()
        for kind, arr in (('hold', held), ('break', brk)):
            for i in np.flatnonzero(arr):
                if i < 130 or i >= n - 20:
                    continue
                r = {'code': code, 'kind': kind, 'date': int(dates[i]),
                     'prior_hold': 0.0 if not np.isfinite(hs[i]) else hs[i]}
                for H in HORIZONS:
                    r[f'exc{H}'] = (c[i + H] / c[i] - 1) * 100 - (bpx[i + H] / bpx[i] - 1) * 100
                rows.append(r)
    return pd.DataFrame(rows)


def main():
    ev = pd.read_csv(os.path.join(HERE, 'support_events.csv'), dtype={'code': str})
    bl = pd.read_csv(os.path.join(HERE, 'support_baseline.csv'), dtype={'code': str})
    ev['code'] = ev['code'].str.zfill(6); bl['code'] = bl['code'].str.zfill(6)
    ev = ev.merge(bl, on='code', how='left')
    for H in HORIZONS:
        ev[f'exc{H}'] = ev[f'ret{H}'] - ev[f'bench{H}']
        ev[f'alp{H}'] = ev[f'exc{H}'] - ev[f'base{H}']

    print('### R1. 수성(hold) vs 이탈(break) 대조 — lo60 터치일')
    be = build_break_events(60)
    be.to_csv(os.path.join(HERE, 'support_holdbreak.csv'), index=False)
    for K in (0, 5):
        s = be[be.prior_hold >= K]
        print(f'\n-- 과거 수성 {K}회 이상 --')
        t = s.groupby('kind').agg(n=('date', 'size'), **{f'exc{H}': (f'exc{H}', 'mean') for H in HORIZONS})
        print(t.to_string(float_format=lambda v: f'{v:7.3f}'))
        for H in (5, 20):
            a = s[s.kind == 'hold'][f'exc{H}'].dropna()
            b = s[s.kind == 'break'][f'exc{H}'].dropna()
            diff = a.mean() - b.mean()
            se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
            print(f'   H={H:2d}  hold-break = {diff:+.3f}%p  (t={diff/se:+.2f})')

    print('\n### R2~R4. lo60 · 과거 수성 5회 이상 후보')
    s = ev[(ev.level == 'lo60') & (ev.prior_hold >= 5)]
    print(f'이벤트 {len(s)}건 · 종목 {s.code.nunique()}종')
    for H in HORIZONS:
        net = s[f'exc{H}'] - COST
        print(f'  H={H:2d}  알파 {s[f"alp{H}"].mean():+.3f} (t={tstat(s[f"alp{H}"]):+.2f})  '
              f'KODEX초과 {s[f"exc{H}"].mean():+.3f}  비용차감후 {net.mean():+.3f} (t={tstat(net):+.2f})  '
              f'승률 {(net > 0).mean() * 100:.1f}%')

    print('\n-- R2. 종목 잭나이프 (1종목씩 제거, H=5 알파) --')
    codes = s.code.unique()
    vals = [s[s.code != c]['alp5'].mean() for c in codes]
    print(f'   최소 {min(vals):+.3f} / 중앙 {np.median(vals):+.3f} / 최대 {max(vals):+.3f}  '
          f'→ 부호 유지 {"O" if min(vals) > 0 else "X"}')
    imp = sorted(zip(codes, vals), key=lambda x: x[1])[:3]
    nm = ev.set_index('code')['name'].to_dict()
    for c, v in imp:
        print(f'   제거 시 최대 악화: {nm.get(c, c)} ({c}) → {v:+.3f}')

    print('\n-- R3. 분기별 안정성 (H=5) --')
    s = s.copy()
    s['q'] = (s.date // 100).map(lambda ym: f'{ym//100}Q{(ym%100-1)//3+1}')
    q = s.groupby('q').agg(n=('date', 'size'), alp5=('alp5', 'mean'), exc5=('exc5', 'mean'))
    print(q.to_string(float_format=lambda v: f'{v:7.3f}'))
    print(f'   알파 양수 분기 {int((q.alp5 > 0).sum())}/{len(q)}')

    print('\n-- R5. 다중검정 --')
    ntrial = 8 * 4 * 5
    from math import erfc, sqrt
    t5 = tstat(s['alp5'])
    p = erfc(abs(t5) / sqrt(2))
    print(f'   시행 조합 수 {ntrial} · lo60/K5/H5 t={t5:+.2f} · 단순 p={p:.4f} · '
          f'Bonferroni p={min(1, p*ntrial):.3f} → {"통과" if p*ntrial < 0.05 else "미통과"}')


if __name__ == '__main__':
    main()
