#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bt_sbd_robust_20260819.py — Rule SBD3(업종 상승집중도 게이트) 4관문 정밀 검정.

`bt_sector_breadth_20260819.py` 에서 SBD3 가 2년(583일) 표본에서
R2(3분할)·R3(정의 교체)·R5(꼬리) 를 통과했다. 승격 판정 전에 남은 관문을 돌린다.

  R1  파라미터 고원 — 임계(q) 축 + **lag 축**. SBR·SRV·BRD 가 전부 lag 축에서 무너졌다.
  R4  플라시보 순열 — 업종 라벨을 무작위로 섞어 200회 재계산, 경험적 p.
  보조 국면 분해 — 게이트 발동일/미발동일을 나눠 이득의 출처를 확인.

lag=1 이 실전 기준이지만(§4-5) **현상 자체가 지연에 따라 완만히 감쇠하는지**를 보려면
lag 0·2·3 을 함께 봐야 한다. 한 점만 솟으면 인공물이다.

성능 — mom20 랭킹·익일수익률은 변형과 무관하므로 **하루당 한 번만** 계산해 캐시한다.
순열 200회는 KRX 원본을 다시 읽지 않고 메모리 배열에서 라벨만 갈아끼운다.
"""
import csv
import os
import random
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('SBD_KRX', '/tmp/krx_stock_panel_2y.csv')
os.environ.setdefault('SBD_ETF', os.path.join(HERE, 'panel_ohlc_2y.csv'))

import bt_sector_breadth_20260819 as B                       # noqa: E402

MIN_SEC = B.MIN_SEC
NPICK = B.NPICK


# ─────────────────────────────── 원본 1회 로드

def load_krx_rows():
    """(date, code, up) 만 남긴다 — 순열 때 라벨만 갈아끼우면 된다."""
    rows = []
    for r in csv.DictReader(open(os.environ['SBD_KRX'], encoding='utf-8')):
        try:
            rows.append((r['date'], r['code'], float(r['chg_pct']) > 0))
        except (TypeError, ValueError):
            continue
    return rows


def hhi_series(rows, smap):
    """일자 → 상승종목의 업종 집중도(HHI × 업종수)."""
    day = defaultdict(lambda: defaultdict(lambda: [0, 0]))   # [상승수, 전체수]
    for d, c, up in rows:
        s = smap.get(c)
        if s is None:
            continue
        v = day[d][s]
        v[1] += 1
        if up:
            v[0] += 1
    out = {}
    for d, secs in day.items():
        ups = [u for u, n in secs.values() if n >= MIN_SEC]
        if len(ups) < 5:
            continue
        tot = sum(ups) or 1.0
        out[d] = sum((u / tot) ** 2 for u in ups) * len(ups)
    return out


# ─────────────────────────────── 채점 캐시

def build_cache(px, names, dates):
    """하루당 (mom20 랭킹 코드리스트, 익일수익률 dict, 벤치수익률)."""
    idx = {d: i for i, d in enumerate(dates)}
    cache = []
    for i, d in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        bm = B.fwd(px, B.BENCH, d, nxt)
        if bm is None:
            continue
        cands = []
        for code in px:
            if not B.eligible(names.get(code, '')):
                continue
            j = idx[d]
            if j < B.MOM or j < 3:
                continue
            a, b = px[code].get(dates[j - B.MOM]), px[code].get(d)
            if not (a and b):
                continue
            c1, c3 = px[code].get(dates[j - 1]), px[code].get(dates[j - 3])
            if c1 and c3 and ((b / c1 - 1) * 100 > 10 or (b / c3 - 1) * 100 > 20):
                continue
            cands.append(((b / a - 1) * 100, code))
        if len(cands) < NPICK:
            continue
        cands.sort(reverse=True)
        top = [c for _, c in cands[:NPICK]]
        bot = [c for _, c in cands[-NPICK:]]
        rt = {c: B.fwd(px, c, d, nxt) for c in set(top) | set(bot)}
        if any(v is None for v in rt.values()):
            continue
        cache.append((d, top, bot, rt, bm))
    return cache


def score(cache, hhi, hdates, thr, lag):
    """thr 미만(집중도 낮음)이면 역모멘텀. 반환 (날짜, 벤치대비 %p) 리스트."""
    pos = {d: i for i, d in enumerate(hdates)}
    res = []
    for d, top, bot, rt, bm in cache:
        ds = [x for x in hdates if x <= d]
        pick = top
        if len(ds) >= lag + 1:
            h = hhi.get(ds[-1 - lag])
            if h is not None and h < thr:
                pick = bot
        res.append((d, sum(rt[c] for c in pick) / NPICK - bm))
    return res


def stat(res):
    return B.stat(res, '')


def main():
    px, names = B.load_etf(os.environ['SBD_ETF'])
    maps = B.load_sector_maps()
    dates_all = sorted({d for c in px for d in px[c]})
    rows = load_krx_rows()
    print(f'KRX 원본 {len(rows):,}행 · ETF {len(px)}종 {len(dates_all)}일\n')

    for tag in ('YF', 'DART'):
        smap = maps[tag]
        hhi = hhi_series(rows, smap)
        hdates = sorted(hhi)
        dates = [d for d in dates_all if d >= hdates[1]]
        cache = build_cache(px, names, dates)
        base = stat([(d, sum(rt[c] for c in top) / NPICK - bm)
                     for d, top, _, rt, bm in cache])
        vals = sorted(hhi.values())
        q = lambda p: vals[int(len(vals) * p)]

        print(f'=== [{tag}] R1 파라미터 고원 — 임계 q × lag (Δ vs baseline) ===')
        print(f'  baseline n={base["n"]} full{base["mean"]:+.4f} '
              f'f1{base["f1"]:+.3f} f2{base["f2"]:+.3f} f3{base["f3"]:+.3f}')
        print('   q / lag ' + ' '.join(f'{l:>9d}' for l in (0, 1, 2, 3)))
        grid = {}
        for p in (0.30, 0.40, 0.50, 0.60):
            row = []
            for lag in (0, 1, 2, 3):
                s = stat(score(cache, hhi, hdates, q(p), lag))
                grid[(p, lag)] = s
                row.append(f'{s["mean"] - base["mean"]:+9.4f}')
            print(f'  q{int(p*100):>7d} ' + ' '.join(row))
        print(f'  격자 16점 중 baseline 초과 '
              f'{sum(1 for v in grid.values() if v["mean"] > base["mean"])}점')

        s = grid[(0.50, 1)]
        real = s['mean'] - base['mean']
        print(f'--- [{tag}] R4 플라시보 순열 (업종 라벨 셔플 200회 · q50 · lag1) ---')
        codes = list(smap)
        labels = [smap[c] for c in codes]
        rnd = random.Random(20260819)
        null = []
        for _ in range(200):
            rnd.shuffle(labels)
            h2 = hhi_series(rows, dict(zip(codes, labels)))
            d2 = sorted(h2)
            v2 = sorted(h2.values())
            null.append(stat(score(cache, h2, d2, v2[int(len(v2) * 0.50)], 1))['mean']
                        - base['mean'])
        null.sort()
        p95 = null[int(len(null) * 0.95)]
        pval = sum(1 for x in null if x >= real) / len(null)
        print(f'  실제 Δ{real:+.4f} · 귀무 평균{statistics.mean(null):+.4f} '
              f'sd{statistics.pstdev(null):.4f} 95분위{p95:+.4f} → 경험적 p = {pval:.3f}')

        bmap = {d: sum(rt[c] for c in top) / NPICK - bm
                for d, top, _, rt, bm in cache}
        fire = [(d, v - bmap[d]) for d, v in s['res'] if abs(v - bmap[d]) > 1e-9]
        if fire:
            fv = [x for _, x in fire]
            print(f'  게이트 발동일 {len(fire)}일 / {len(s["res"])}일 · '
                  f'발동일 평균차{statistics.mean(fv):+.4f} · '
                  f'승률{sum(1 for x in fv if x > 0)/len(fv)*100:.1f}% · '
                  f'중앙값{statistics.median(fv):+.4f}')
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
