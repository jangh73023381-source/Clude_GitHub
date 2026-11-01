#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_attn.py — '정보(검색 관심도) 가중치' 축 7년 검정. 조회 전용.

선등록 설계(착수 전 고정):
  · 판정 패널 7년 panel_ohlc_long.csv (§4-5)
  · baseline = v2.9 Rule LV (mom20 pool30 · Rule H · σ20 하위 5), 1차 지표 = KODEX200 대비 %p/일, 비용 0
  · 관심도 attn(sector,D) = log( MA_a(search ..D-1) / MA_b(search ..D-1) )  ★D-1까지만(실전 조달)
  · 변형 A 게이트 / B 블렌드 / C 배제 / D 급증
  · 무관 신호 대조군 = placebo_search.csv 로 동일 규칙
"""
import csv, os, sys, math, statistics, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BT = os.path.dirname(HERE); LOOP = os.path.dirname(BT)
sys.path.insert(0, os.path.join(LOOP, 'references', 'scripts'))
from universe_filters import eligible          # noqa
import etf_sector_map as sm                    # noqa

LONG = os.path.join(BT, 'panel_ohlc_long.csv')
BENCH, NPICK, MOM = '069500', 5, 20
LV_POOL, LV_K = 30, 20


def load_px():
    px, names = defaultdict(dict), {}
    r = csv.reader(open(LONG, encoding='utf-8')); h = next(r)
    ic, inm, idt, icl = h.index('code'), h.index('name'), h.index('date'), h.index('close')
    for row in r:
        try: px[row[ic]][row[idt]] = float(row[icl])
        except ValueError: continue
        names[row[ic]] = row[inm]
    return px, names


def load_search(fn):
    r = csv.reader(open(os.path.join(HERE, fn), encoding='utf-8'))
    cols = next(r)[1:]
    ser = {c: {} for c in cols}
    for row in r:
        for c, v in zip(cols, row[1:]):
            if v: ser[c][row[0]] = float(v)
    return ser, cols


def attn_scores(ser, a, b):
    """{col: {달력일: log(MA_a/MA_b)}} — 그 날짜까지 포함해 계산(사용 시 D-1로 참조)."""
    out = {}
    for c, s in ser.items():
        ds = sorted(s); vals = [s[d] for d in ds]; o = {}
        for i in range(len(ds)):
            if i < b: continue
            ma = sum(vals[i - a + 1:i + 1]) / a
            mb = sum(vals[i - b + 1:i + 1]) / b
            o[ds[i]] = math.log(ma / mb) if ma > 0 and mb > 0 else 0.0
        out[c] = o
    return out


def prev_cal(d):
    from datetime import date, timedelta
    dd = date(int(d[:4]), int(d[4:6]), int(d[6:])) - timedelta(days=1)
    return dd.strftime('%Y%m%d')


def build_cands(px, names, dates):
    out = {}
    for i, d in enumerate(dates):
        if i < max(MOM, LV_K) + 1: continue
        lst = []
        for c in px:
            nm = names.get(c, '')
            if not eligible(nm): continue
            a, b = px[c].get(dates[i - MOM]), px[c].get(d)
            if not (a and b): continue
            c1, c3 = px[c].get(dates[i - 1]), px[c].get(dates[i - 3])
            if not (c1 and c3): continue
            if (b / c1 - 1) * 100 > 10 or (b / c3 - 1) * 100 > 20: continue   # Rule H
            rets, ok = [], True
            for k in range(LV_K):
                p0, p1 = px[c].get(dates[i - k - 1]), px[c].get(dates[i - k])
                if not (p0 and p1): ok = False; break
                rets.append((p1 / p0 - 1) * 100)
            if not ok: continue
            lst.append(((b / a - 1) * 100, c, statistics.stdev(rets), sm.sector(nm)))
        lst.sort(key=lambda x: -x[0])
        out[d] = lst
    return out


def fwd(px, c, d, n):
    a, b = px[c].get(d), px[c].get(n)
    return None if not (a and b) else (b / a - 1) * 100


def a_of(sc, sector, d):
    """선정일 D 에 쓸 관심도 = D-1 달력일까지의 값."""
    s = sc.get(sector)
    if not s: return 0.0
    k = prev_cal(d)
    for _ in range(7):
        if k in s: return s[k]
        k = prev_cal(k)
    return 0.0


def mk_picker(kind, param, sc):
    def base_lv(pool): return [x[1] for x in sorted(pool, key=lambda x: x[2])[:NPICK]]
    def f(cand, d):
        pool = cand[:LV_POOL]
        if len(pool) < NPICK: return [x[1] for x in pool]
        if kind == 'LV':  return base_lv(pool)
        if kind == 'MOM': return [x[1] for x in cand[:NPICK]]
        at = {x[1]: a_of(sc, x[3], d) for x in pool}
        if kind == 'A':   # 관심 상위 param 종으로 좁힌 뒤 저변동 5
            keep = sorted(pool, key=lambda x: -at[x[1]])[:param]
            return base_lv(keep if len(keep) >= NPICK else pool)
        if kind == 'C':   # 관심 하위 param 종 제외
            keep = sorted(pool, key=lambda x: -at[x[1]])[:max(NPICK, len(pool) - param)]
            return base_lv(keep)
        if kind == 'B':   # 랭크 블렌드 (w=param)
            ra = {c: i for i, (c) in enumerate([x[1] for x in sorted(pool, key=lambda x: -at[x[1]])])}
            rs = {c: i for i, (c) in enumerate([x[1] for x in sorted(pool, key=lambda x: x[2])])}
            sc2 = sorted(pool, key=lambda x: param * ra[x[1]] + (1 - param) * rs[x[1]])
            return [x[1] for x in sc2[:NPICK]]
        raise ValueError(kind)
    return f


def series(px, dates, cands, picker):
    out = []
    for i, d in enumerate(dates[:-1]):
        n = dates[i + 1]
        bm = fwd(px, BENCH, d, n); cd = cands.get(d)
        if bm is None or not cd or len(cd) < NPICK: continue
        rs = [fwd(px, c, d, n) for c in picker(cd, d)]
        rs = [x for x in rs if x is not None]
        if len(rs) < NPICK: continue
        out.append((d, sum(rs) / len(rs) - bm))
    return out


def tstat(v):
    return statistics.mean(v) / (statistics.stdev(v) / len(v) ** 0.5) if len(v) > 2 else float('nan')


def compare(base, cand):
    bd, cdd = dict(base), dict(cand)
    days = sorted(set(bd) & set(cdd))
    b = [bd[d] for d in days]; c = [cdd[d] for d in days]
    diff = [x - y for x, y in zip(c, b)]
    n = len(days); t3 = n // 3
    folds = [statistics.mean(diff[s:e]) for s, e in [(0, t3), (t3, 2 * t3), (2 * t3, n)]]
    s = sorted(diff, reverse=True)
    return {'n': n, 'cand': statistics.mean(c), 'base': statistics.mean(b),
            'diff': statistics.mean(diff), 't': tstat(diff), 'folds': folds,
            'top3': statistics.mean(s[3:]), 'med': statistics.median(diff)}
