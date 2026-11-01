# -*- coding: utf-8 -*-
"""2026-07-31 — 망치형/역망치형 캔들 검정 (사용자 제안).

가설: 아래꼬리가 긴 망치형은 상승, 윗꼬리가 긴 형태(유성형)는 하락 가능성이 크다.

정의 (하루 캔들, rng = 고가-저가):
  body  = |종가-시가|
  아래꼬리 = min(시가,종가) - 저가
  윗꼬리  = 고가 - max(시가,종가)
  망치형   : 아래꼬리 >= 2×body 이고 윗꼬리 <= 0.10×rng
  유성형   : 윗꼬리  >= 2×body 이고 아래꼬리 <= 0.10×rng

**시장 제거**: 그날 전체 ETF의 횡단면 평균 수익률을 뺀다. 안 그러면 "시장이 오른 날
망치형이 많았다"를 패턴의 예측력으로 오인한다.

**군집 보정**: 같은 날 관측치는 서로 상관되어 있으므로, 개별 관측이 아니라
**일별 평균을 만든 뒤 날짜 간 t검정**을 한다. 이걸 빼먹으면 t값이 3~5배 부풀려진다.

룩어헤드 금지 — 패턴은 D 종가까지, 수익률은 D+1 이후로 시점이 분리돼 있다.
"""
import csv
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from universe_filters import is_cash, is_deriv  # noqa: E402

PANEL = os.path.join(HERE, 'panel_ohlc_2y.csv')


def load():
    bar, nm = defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            o, h, l, c = (float(r['open']), float(r['high']),
                          float(r['low']), float(r['close']))
        except (ValueError, KeyError):
            continue
        if min(o, h, l, c) <= 0 or h < l:
            continue
        nm[r['code']] = r['name']
        bar[r['code']][r['date']] = (o, h, l, c)
    keep = {c for c in bar if not is_deriv(nm[c]) and not is_cash(nm[c])}
    bar = {c: v for c, v in bar.items() if c in keep}
    return bar, nm, sorted({d for v in bar.values() for d in v})


def shape(b):
    o, h, l, c = b
    rng = h - l
    if rng <= 0:
        return None
    body = abs(c - o)
    up = h - max(o, c)
    lo = min(o, c) - l
    return {'rng': rng, 'body': body, 'up': up, 'lo': lo,
            'lo_r': lo / rng, 'up_r': up / rng, 'body_r': body / rng}


def is_hammer(s):
    return s['lo'] >= 2 * s['body'] and s['up'] <= 0.10 * s['rng']


def is_star(s):
    return s['up'] >= 2 * s['body'] and s['lo'] <= 0.10 * s['rng']


def daily_t(groups):
    """일별 평균의 평균과 t (날짜 군집 보정)."""
    days = [statistics.fmean(v) for v in groups.values() if v]
    if len(days) < 5:
        return None
    m = statistics.fmean(days)
    sd = statistics.stdev(days)
    return m, sd / len(days) ** 0.5, m / (sd / len(days) ** 0.5), len(days), \
        sum(len(v) for v in groups.values())


def main():
    bar, nm, dates = load()
    di = {d: i for i, d in enumerate(dates)}
    print(f'패널 {len(bar)}종 · {len(dates)}거래일 ({dates[0]}~{dates[-1]})')

    for H in (1, 2, 3, 5):
        # 그날 횡단면 평균을 뺀 초과수익
        pool = defaultdict(list)          # date -> [(code, excess, shape, trend)]
        for i in range(20, len(dates) - H):
            d, e = dates[i], dates[i + H]
            rows = []
            for c, v in bar.items():
                if d not in v or e not in v:
                    continue
                s = shape(v[d])
                if s is None:
                    continue
                r = v[e][3] / v[d][3] - 1
                d20 = dates[i - 20]
                tr = (v[d][3] / v[d20][3] - 1) if d20 in v else None
                rows.append((c, r, s, tr))
            if len(rows) < 30:
                continue
            mkt = statistics.fmean([x[1] for x in rows])
            for c, r, s, tr in rows:
                pool[d].append((c, 100 * (r - mkt), s, tr))

        ham, star, base = defaultdict(list), defaultdict(list), defaultdict(list)
        ham_dn, star_up = defaultdict(list), defaultdict(list)
        for d, rows in pool.items():
            for c, x, s, tr in rows:
                base[d].append(x)
                if is_hammer(s):
                    ham[d].append(x)
                    if tr is not None and tr < 0:      # 고전적 정의: 하락 추세 뒤
                        ham_dn[d].append(x)
                if is_star(s):
                    star[d].append(x)
                    if tr is not None and tr > 0:      # 상승 추세 뒤
                        star_up[d].append(x)

        print(f'\n=== 보유 {H}일 · 시장 제거 후 초과수익(%) · 날짜 군집 보정 t ===')
        print(f'  {"그룹":26s}{"관측":>8s}{"일수":>6s}{"평균":>9s}{"t":>8s}')
        for lab, g in (('전체(기준선)', base), ('망치형', ham),
                       ('망치형 ∩ 20일 하락', ham_dn), ('유성형(윗꼬리)', star),
                       ('유성형 ∩ 20일 상승', star_up)):
            r = daily_t(g)
            if r is None:
                print(f'  {lab:26s}  표본 부족')
                continue
            m, se, t, nd, nobs = r
            print(f'  {lab:26s}{nobs:8d}{nd:6d}{m:+9.3f}{t:+8.2f}')

        if H == 1:                        # 연속 지표의 순위상관(IC)
            print('\n  [연속 지표] 꼬리 비율 vs 익일 초과수익 — 일별 rank IC')
            for key, lab in (('lo_r', '아래꼬리 비율'), ('up_r', '윗꼬리 비율')):
                ics = []
                for d, rows in pool.items():
                    if len(rows) < 20:
                        continue
                    xs = [r[2][key] for r in rows]
                    ys = [r[1] for r in rows]
                    n = len(xs)
                    rx = {v: i for i, v in enumerate(sorted(range(n), key=lambda j: xs[j]))}
                    ry = {v: i for i, v in enumerate(sorted(range(n), key=lambda j: ys[j]))}
                    a = [rx[i] for i in range(n)]
                    b = [ry[i] for i in range(n)]
                    ma, mb = statistics.fmean(a), statistics.fmean(b)
                    num = sum((p - ma) * (q - mb) for p, q in zip(a, b))
                    da = sum((p - ma) ** 2 for p in a) ** 0.5
                    db = sum((q - mb) ** 2 for q in b) ** 0.5
                    if da and db:
                        ics.append(num / (da * db))
                m = statistics.fmean(ics)
                t = m / (statistics.stdev(ics) / len(ics) ** 0.5)
                print(f'    {lab:16s} 평균 IC {m:+.4f} · t {t:+6.2f} · {len(ics)}일')


if __name__ == '__main__':
    main()
