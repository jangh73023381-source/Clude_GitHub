#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""박스권 경로 청산 검정 — 채점 및 과최적화 가드.

지표
  excess = 보유기간 수익률 - KODEX200 동기간 수익률 - 왕복비용 10bp
  t      : 일자 클러스터 t (같은 날 여러 종목이 동시에 잡히면 독립 표본이 아니므로
           날짜 단위로 평균낸 뒤 t를 잰다)
가드
  train/test 2분할 (중앙 날짜) · 종목 잭나이프 · 사후 분해(박스 유형 · 청산 사유)
조회 전용.
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
COST = 0.10
TAGS = ['base', 'top_s2', 'top_s4', 'mid_s2', 'mid_s4']
LABEL = {'base': 'H=5 시간청산(기존)', 'top_s2': '상단청산·손절-2%',
         'top_s4': '상단청산·손절-4%', 'mid_s2': '중간청산·손절-2%',
         'mid_s4': '중간청산·손절-4%'}


def clust_t(df, col):
    """일자 클러스터 t."""
    g = df.groupby('date')[col].mean()
    g = g[np.isfinite(g)]
    if len(g) < 3:
        return np.nan
    return g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))


def prep(ev):
    for t in TAGS:
        ev[f'{t}_exc'] = ev[f'{t}_ret'] - ev[f'{t}_bench'] - COST
    return ev


def summary(ev):
    rows = []
    for t in TAGS:
        e = ev[f'{t}_exc']
        rows.append(dict(청산=LABEL[t], 이벤트=int(e.notna().sum()),
                         초과수익=round(e.mean(), 3), t=round(clust_t(ev, f'{t}_exc'), 2),
                         승률=round((e > 0).mean() * 100, 1),
                         평균보유일=round(ev[f'{t}_days'].mean(), 1),
                         일평균=round(e.mean() / ev[f'{t}_days'].mean(), 4)))
    return pd.DataFrame(rows)


def split_test(ev):
    mid = ev['date'].median()
    tr, te = ev[ev['date'] <= mid], ev[ev['date'] > mid]
    rows = []
    for t in TAGS:
        rows.append(dict(청산=LABEL[t],
                         train=round(tr[f'{t}_exc'].mean(), 3),
                         train_t=round(clust_t(tr, f'{t}_exc'), 2),
                         test=round(te[f'{t}_exc'].mean(), 3),
                         test_t=round(clust_t(te, f'{t}_exc'), 2),
                         판정='부호유지' if tr[f'{t}_exc'].mean() * te[f'{t}_exc'].mean() > 0
                         else '부호반전'))
    return pd.DataFrame(rows)


def jackknife(ev):
    rows = []
    for t in TAGS:
        vals = [ev[ev['code'] != c][f'{t}_exc'].mean() for c in ev['code'].unique()]
        rows.append(dict(청산=LABEL[t], 최소=round(min(vals), 3),
                         중앙=round(float(np.median(vals)), 3), 최대=round(max(vals), 3),
                         부호유지='O' if min(vals) * max(vals) > 0 else 'X'))
    return pd.DataFrame(rows)


def box_type(ev):
    """사후 분해 — 조건으로 걸지 않았음(시행 횟수에 넣지 않는다)."""
    q = ev['slope']
    ev = ev.assign(유형=np.where(q > 0.05, '우상향',
                                 np.where(q < -0.05, '우하향', '횡보')))
    rows = []
    for tp, g in ev.groupby('유형'):
        r = dict(유형=tp, 이벤트=len(g))
        for t in TAGS:
            r[LABEL[t][:6]] = round(g[f'{t}_exc'].mean(), 3)
        rows.append(r)
    return pd.DataFrame(rows).sort_values('이벤트', ascending=False)


def why(ev):
    rows = []
    for t in TAGS[1:]:
        vc = ev[f'{t}_why'].value_counts()
        r = dict(청산=LABEL[t])
        for k in ['target', 'stop', 'cap']:
            n = int(vc.get(k, 0))
            r[k] = f'{n} ({n / len(ev) * 100:.0f}%)'
            r[f'{k}_수익'] = round(ev[ev[f"{t}_why"] == k][f'{t}_exc'].mean(), 2) if n else None
        rows.append(r)
    return pd.DataFrame(rows)


def main():
    ev = prep(pd.read_csv(os.path.join(HERE, 'box_exit_events.csv'), dtype={'code': str}))
    pd.set_option('display.width', 200, 'display.max_columns', 30)
    print(f'표본: 이벤트 {len(ev)}건 · 종목 {ev["code"].nunique()}종 · '
          f'{ev["date"].min()}~{ev["date"].max()}\n')
    print('[1] 청산 규칙별 성과 (KODEX200 대비 %p, 왕복 10bp 차감)')
    print(summary(ev).to_string(index=False), '\n')
    print('[2] train/test 2분할')
    print(split_test(ev).to_string(index=False), '\n')
    print('[3] 종목 잭나이프 (1종씩 제거한 평균 초과수익)')
    print(jackknife(ev).to_string(index=False), '\n')
    print('[4] 청산 사유 분해')
    print(why(ev).to_string(index=False), '\n')
    print('[5] 사후 분해 — 박스 유형별 (조건으로 걸지 않음, 관찰용)')
    print(box_type(ev).to_string(index=False))


if __name__ == '__main__':
    main()
