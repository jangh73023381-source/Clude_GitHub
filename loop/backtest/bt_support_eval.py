#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""지지선 이벤트 평가 — 보유일 스윕 · 준수횟수 컷 · train/test 분할 · 잭나이프.

지표
  excess  = 이벤트 수익률 - KODEX200 동기간 수익률          (벤치 대비)
  alpha   = excess - 그 종목의 무조건 평균 excess           (그 종목 평시 대비)
alpha 가 핵심이다. 지지선이 '타이밍'으로서 값어치가 있는지는 종목 자체의 추세를 빼야 보인다.
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HORIZONS = [1, 3, 5, 10, 20]
KCUTS = [0, 3, 5, 8]


def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return np.nan
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))


def load():
    ev = pd.read_csv(os.path.join(HERE, 'support_events.csv'), dtype={'code': str})
    bl = pd.read_csv(os.path.join(HERE, 'support_baseline.csv'), dtype={'code': str})
    ev['code'] = ev['code'].str.zfill(6)
    bl['code'] = bl['code'].str.zfill(6)
    ev = ev.merge(bl, on='code', how='left')
    for H in HORIZONS:
        ev[f'exc{H}'] = ev[f'ret{H}'] - ev[f'bench{H}']
        ev[f'alp{H}'] = ev[f'exc{H}'] - ev[f'base{H}']
    ev['respect'] = ev['prior_hold'] / (ev['prior_hold'] + ev['prior_break']).replace(0, np.nan)
    return ev


def sweep(ev, tag, f=None):
    rows = []
    for lvl in sorted(ev['level'].unique()):
        for K in KCUTS:
            s = ev[(ev.level == lvl) & (ev.prior_hold >= K)]
            if f is not None:
                s = s[f(s)]
            if len(s) < 30:
                continue
            r = {'level': lvl, 'K': K, 'n': len(s), 'codes': s.code.nunique()}
            for H in HORIZONS:
                r[f'exc{H}'] = s[f'exc{H}'].mean()
                r[f'alp{H}'] = s[f'alp{H}'].mean()
                r[f't{H}'] = tstat(s[f'alp{H}'])
                r[f'win{H}'] = (s[f'alp{H}'] > 0).mean() * 100
            rows.append(r)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(HERE, f'support_sweep_{tag}.csv'), index=False)
    return out


def show(df, cols, title, sort=None, n=12):
    print(f'\n=== {title} ===')
    d = df.sort_values(sort, ascending=False) if sort else df
    print(d[cols].head(n).to_string(index=False, float_format=lambda v: f'{v:7.3f}'))


def main():
    ev = load()
    print(f'이벤트 {len(ev)}건 · 종목 {ev.code.nunique()} · 기간 {ev.date.min()}~{ev.date.max()}')
    print('\n지지선 정의별 이벤트 수:')
    print(ev.groupby('level').size().to_string())

    full = sweep(ev, 'full')
    cols = ['level', 'K', 'n', 'codes', 'alp1', 't1', 'alp3', 't3', 'alp5', 't5',
            'alp10', 't10', 'alp20', 't20']
    show(full, cols, '전체 구간 — 종목 평시 대비 알파 (%p)', sort='alp5', n=40)

    show(full, ['level', 'K', 'n', 'exc1', 'exc3', 'exc5', 'exc10', 'exc20'],
         '전체 구간 — KODEX200 대비 초과수익 (%p)', sort='exc5', n=40)

    # train / test 분할
    mid = int(np.percentile(ev['date'], 50))
    tr = sweep(ev[ev.date < mid], 'train')
    te = sweep(ev[ev.date >= mid], 'test')
    m = tr.merge(te, on=['level', 'K'], suffixes=('_tr', '_te'))
    print(f'\n=== train/test 분할 (경계 {mid}) ===')
    for H in (3, 5, 20):
        c = ['level', 'K', f'n_tr', f'alp{H}_tr', f't{H}_tr', 'n_te', f'alp{H}_te', f't{H}_te']
        print(f'\n-- H={H}일 --')
        print(m.sort_values(f'alp{H}_tr', ascending=False)[c].head(10)
              .to_string(index=False, float_format=lambda v: f'{v:7.3f}'))

    # 종목별 준수율 랭킹 (레벨 통합)
    g = ev.groupby(['code', 'name']).agg(
        n=('date', 'size'), hold=('prior_hold', 'mean'),
        alp5=('alp5', 'mean'), alp20=('alp20', 'mean'), exc5=('exc5', 'mean')).reset_index()
    g = g[g.n >= 20].sort_values('alp5', ascending=False)
    g.to_csv(os.path.join(HERE, 'support_by_code.csv'), index=False)
    print('\n=== 종목별 (이벤트 20건 이상) — 알파 상위 15 ===')
    print(g.head(15).to_string(index=False, float_format=lambda v: f'{v:7.3f}'))
    print('\n=== 종목별 — 알파 하위 10 ===')
    print(g.tail(10).to_string(index=False, float_format=lambda v: f'{v:7.3f}'))


if __name__ == '__main__':
    main()
