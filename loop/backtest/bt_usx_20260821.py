#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rule USX — 전일 미국 동일테마 지수 수익률을 mom20 랭킹에 횡단면 가산 (7년 패널).

2026-08-19 검증관 지정 '다음 회차 우선 시도축 (1)'.
기각된 Rule U(해외추종형 캡)·Rule FF(해외벤치마크 역행 하향)와 형태가 다르다 —
캡·하향이 아니라 **점수 가산**이고, 대상이 해외추종형만이 아니라 국내 테마 ETF 전체다.
조달: 미국 날짜 D 세션은 05:00 KST(D+1) 마감 → 선정 시각 T=D+1 06:00 확보 가능(§4-6).
"""
import csv, json, os, random, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'references', 'scripts'))
from universe_filters import eligible  # noqa: E402

LONG = os.path.join(HERE, 'panel_ohlc_long.csv')
US = os.path.join(HERE, 'us_theme_close.csv')
CACHE = os.path.join(HERE, '_usx_cache.json')
BENCH, NPICK, MOM = '069500', 5, 20

KW = [
    (('반도체', 'HBM', 'AI반도체', '메모리'), 'SOX'),
    (('바이오', '헬스케어', '제약'), 'BIO'),
    (('태양광', 'ESS', '신재생', '탄소'), 'SOLAR'),
    (('방산', '우주항공', '항공우주', 'K방산'), 'DEF'),
    (('2차전지', '배터리', '리튬'), 'BATT'),
    (('로봇', '휴머노이드'), 'ROBO'),
    (('금현물', '골드', '은선물', '금선물'), 'GOLD'),
    (('원자력', 'SMR'), 'NUKE'),
    (('은행', '금융', '증권', '보험'), 'BANK'),
    (('자동차',), 'AUTO'),
    (('화장품', '필수소비재', '소비재'), 'COS'),
    (('건설', '인프라', '기계'), 'CONS'),
    (('차이나', '중국', '항셍'), 'CHINA'),
    (('나스닥', '미국테크', 'IT', '테크', '소프트웨어', '인터넷', '게임', '미디어'), 'QQQ'),
]
THEMES = sorted({t for _, t in KW} | {'SPY'})


def theme_of(name):
    for kws, th in KW:
        for k in kws:
            if k in name:
                return th
    return 'SPY'


def build_cache():
    px, names = defaultdict(dict), {}
    r = csv.reader(open(LONG, encoding='utf-8')); h = next(r)
    ic, inm, idt, icl = h.index('code'), h.index('name'), h.index('date'), h.index('close')
    for row in r:
        try:
            px[row[ic]][row[idt]] = float(row[icl])
        except ValueError:
            continue
        names[row[ic]] = row[inm]
    dates = sorted({d for m in px.values() for d in m})
    # 미국 테마 수익률
    cl = defaultdict(dict)
    r = csv.reader(open(US, encoding='utf-8')); next(r)
    for th, tk, d, c in r:
        cl[th][d] = float(c)
    usret = {}
    for th, m in cl.items():
        ds = sorted(m)
        usret[th] = [(ds[i], (m[ds[i]] / m[ds[i - 1]] - 1) * 100) for i in range(1, len(ds))]

    def us_at(th, d, lag):
        arr = usret.get(th, [])
        lo, hi = 0, len(arr)
        while lo < hi:                       # d 이하 마지막 인덱스
            mid = (lo + hi) // 2
            if arr[mid][0] <= d:
                lo = mid + 1
            else:
                hi = mid
        i = lo - 1 - lag
        return arr[i][1] if i >= 0 else None

    days = []
    for i in range(MOM, len(dates) - 1):
        d, n = dates[i], dates[i + 1]
        ba, bb = px[BENCH].get(d), px[BENCH].get(n)
        if not (ba and bb):
            continue
        bench = (bb / ba - 1) * 100
        rows = []
        for c in px:
            nm = names.get(c, '')
            if not eligible(nm):
                continue
            a, b = px[c].get(dates[i - MOM]), px[c].get(d)
            if not (a and b):
                continue
            c1, c3 = px[c].get(dates[i - 1]), px[c].get(dates[i - 3])
            if c1 and c3 and ((b / c1 - 1) * 100 > 10 or (b / c3 - 1) * 100 > 20):
                continue
            nx = px[c].get(n)
            if not nx:
                continue
            rows.append([(b / a - 1) * 100, theme_of(nm), (nx / b - 1) * 100, c])
        if len(rows) < NPICK:
            continue
        us = {}
        for lag in (0, 1, 2, 3):
            us[lag] = {th: us_at(th, d, lag) for th in THEMES}
        days.append({'d': d, 'bench': bench, 'rows': rows, 'us': us})
    json.dump(days, open(CACHE, 'w'))
    return days


def load_days():
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    return build_cache()


def run(days, lam, lag, cap=None, shuffle_map=None):
    out = []
    for day in days:
        us = day['us'][str(lag)] if isinstance(next(iter(day['us'])), str) else day['us'][lag]
        sc = []
        for mom, th, fwd, c in day['rows']:
            s = mom
            if lam:
                t2 = shuffle_map[th] if shuffle_map else th
                u = us.get(t2)
                if u is not None:
                    if cap is not None:
                        u = max(-cap, min(cap, u))
                    s = mom + lam * u
            sc.append((s, fwd))
        sc.sort(reverse=True)
        top = sc[:NPICK]
        out.append((day['d'], sum(f for _, f in top) / len(top) - day['bench']))
    return out


def avg(x):
    return sum(r for _, r in x) / len(x) if x else float('nan')


def folds(x, k=3):
    n = len(x) // k
    return [x[i * n:(i + 1) * n if i < k - 1 else len(x)] for i in range(k)]


def main():
    days = load_days()
    base = run(days, 0, 0)
    bm = avg(base); bf = [avg(f) for f in folds(base)]
    print(f'baseline 일평균 초과 {bm:+.4f}%p (n={len(base)})  fold {bf[0]:+.4f}/{bf[1]:+.4f}/{bf[2]:+.4f}')
    print()
    print('=== R1 파라미터 고원 (lam × lag) ===  [baseline %+.4f]' % bm)
    print(f'{"lam":>5} | ' + ' | '.join(f'lag{l}'.rjust(9) for l in (0, 1, 2, 3)))
    grid = {}
    for lam in (0.1, 0.2, 0.3, 0.5, 1.0, 2.0):
        cells = []
        for lag in (0, 1, 2, 3):
            m = avg(run(days, lam, lag))
            grid[f'{lam}_{lag}'] = m
            cells.append(('*' if m > bm else ' ') + f'{m:+.4f}'.rjust(8))
        print(f'{lam:>5} | ' + ' | '.join(cells))
    json.dump({'base': bm, 'base_folds': bf, 'grid': grid, 'n': len(base)},
              open(os.path.join(HERE, '_usx_grid.json'), 'w'))
    print('\n(* = baseline 초과)')


if __name__ == '__main__':
    main()
