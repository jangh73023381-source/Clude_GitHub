# -*- coding: utf-8 -*-
"""2026-08-03 — Rule CB(중기 종가베팅 진입 밴드)를 ATR로 정규화하면 나아지는가.

현행: 당일 등락률이 -0.5% ~ +1.5% 인 후보만 종가 매수 (고정 %).
대안: 당일 등락률을 그 종목의 ATR14% 로 나눈 표준화 값(z)이 -a ~ +b 인 후보만 매수.
      ATR 2% 짜리의 +1.5% 와 ATR 10% 짜리의 +1.5% 는 전혀 다른 사건이라는 문제 제기.

선정은 현행 확정축 mom150 상위 5종. 청산은 상위5 탈락 첫날 종가(기간조건 없음, 2026-08-03 개정).
벤치 KODEX200 대비, 왕복 10bp.
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
BENCH, COST = '069500', 0.0010


def load():
    bar, nm = defaultdict(dict), {}
    for r in csv.DictReader(open(PANEL, encoding='utf-8')):
        try:
            o, h, l, c = (float(r['open']), float(r['high']),
                          float(r['low']), float(r['close']))
        except (ValueError, KeyError):
            continue
        if min(o, h, l, c) <= 0:
            continue
        nm[r['code']] = r['name']
        bar[r['code']][r['date']] = (o, h, l, c)
    bar = {c: v for c, v in bar.items() if not is_deriv(nm[c]) and not is_cash(nm[c])}
    return bar, nm, sorted({d for v in bar.values() for d in v})


def atr_pct(bar, c, d, di, dates, n=14):
    i = di[d]
    if i < n:
        return None
    trs = []
    for j in range(i - n + 1, i + 1):
        cur, prv = bar[c].get(dates[j]), bar[c].get(dates[j - 1])
        if not cur or not prv:
            return None
        trs.append(max(cur[1] - cur[2], abs(cur[1] - prv[3]), abs(cur[2] - prv[3])))
    return (sum(trs) / n) / bar[c][d][3]


def mom150(bar, d, di, dates, k=150):
    i = di[d]
    if i < k:
        return []
    cs = []
    for c, v in bar.items():
        a, b = v.get(dates[i - k]), v.get(d)
        if a and b:
            cs.append((b[3] / a[3] - 1.0, c))
    cs.sort(reverse=True)
    return [c for _, c in cs[:5]]


def run(bar, nm, dates, di, mode, lo, hi):
    """lo/hi: mode='fix'면 등락률 %, mode='atr'면 ATR 배수."""
    held = {}          # code -> 진입가
    daily = []
    for i in range(151, len(dates) - 1):
        d, nxt = dates[i], dates[i + 1]
        if d not in bar[BENCH] or nxt not in bar[BENCH]:
            continue
        top = set(mom150(bar, d, di, dates))
        if not top:
            continue
        # 오늘 종가 기준 포트 수익률(어제 종가 → 오늘 종가) 기록
        rs = []
        for c, _ in held.items():
            a, b = bar[c].get(dates[i - 1]), bar[c].get(d)
            if a and b:
                rs.append(b[3] / a[3] - 1)
        if rs:
            bch = bar[BENCH][d][3] / bar[BENCH][dates[i - 1]][3] - 1
            daily.append(100 * (sum(rs) / len(rs) - bch))
        # 탈락 청산
        for c in [c for c in held if c not in top]:
            del held[c]
        # 신규 진입 판정
        for c in top:
            if c in held or d not in bar[c]:
                continue
            prv = bar[c].get(dates[i - 1])
            if not prv:
                continue
            chg = bar[c][d][3] / prv[3] - 1
            if mode == 'fix':
                ok = lo <= chg * 100 <= hi
            else:
                a = atr_pct(bar, c, d, di, dates)
                if not a:
                    continue
                z = chg / a
                ok = lo <= z <= hi
            if ok:
                held[c] = bar[c][d][3]
    return daily


def rep(lab, v):
    if not v:
        print(f'  {lab:30s}  (표본 없음)')
        return
    mu = statistics.fmean(v)
    sd = statistics.stdev(v)
    print(f'  {lab:30s}{mu:+9.4f}{sum(1 for x in v if x > 0)/len(v):8.1%}'
          f'{mu/(sd/len(v)**0.5):8.2f}{len(v):7d}')


def main():
    bar, nm, dates = load()
    di = {d: i for i, d in enumerate(dates)}
    print('중기 mom150 · Rule CB 밴드 방식 비교 (벤치 대비 %p/일, 보유일 기준)')
    print(f'  {"방식":30s}{"평균초과":>9s}{"승률":>8s}{"t":>8s}{"보유일":>7s}')
    print('  ' + '-' * 62)
    rep('밴드 없음(전량 매수)', run(bar, nm, dates, di, 'fix', -99, 99))
    rep('고정 -0.5% ~ +1.5% (현행)', run(bar, nm, dates, di, 'fix', -0.5, 1.5))
    for lo, hi in ((-0.2, 0.4), (-0.15, 0.45), (-0.3, 0.6), (-0.5, 1.0)):
        rep(f'ATR배수 {lo:+.2f} ~ {hi:+.2f}', run(bar, nm, dates, di, 'atr', lo, hi))


if __name__ == '__main__':
    main()
